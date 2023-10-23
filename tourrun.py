from tournament import Tournament
from joycontrol.protocol import controller_protocol_factory
from joycontrol.server import create_hid_server
from joycontrol.controller import Controller
import logging
from joycontrol.controller_state import ControllerState
from joycontrol.controller_state import button_push
from joycontrol.ScriptRunner import ScriptRunner
from joycontrol import logging_default as log, utils
import os
import webhook
import io
import json
import ftplib
import asyncio
from joycontrol.nfc_tag import NFCTag
import socket
import csv
import match_data
import time

if not os.path.exists("config.json"):
    config = {}
    config["tour_url"] = input("Input your tournament's url.\n")
    config["ip"] = input("Input your switch's IP address.\n")
    config["webhook_url"] = { "url": input("Input the url of your webhook.\n"), "thread_id": input("Input the thread id of the tournament channel, or None if not present") }
    config["webhook_name"] = input("Input the preferred name of your webhook.\n")
    config["webhook_avatar_url"] = input(
        "Input the link to the profile picture you would like the bot to use:\n"
    )
    config["challonge_username"] = input("Please input your challonge username.\n")
    config["challonge_api_key"] = input("Please input your challonge api key.\n")
    config["save_after_match"] = False
    with open("config.json", "w+") as cfg:
        json.dump(config, cfg, indent=4)

with open("config.json") as cfg:
    config: dict = json.load(cfg)
    if type(config["webhook_url"]) != list:
        config["webhook_url"] = [
            config["webhook_url"],
        ]
    with open("config.json", "w+") as cfg:
        json.dump(config, cfg, indent=4)

ip = config["ip"]
port = "6969"
bindict = {}
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
socket_connected = False


async def restart_match(controller_state, fp1_tag, fp2_tag):
    global s
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    await load_match(controller_state, True, fp1_tag, fp2_tag)


def replace_bad_character(letter):
    if letter in "%:/'\"\\[]<>*?":
        return "+"
    else:
        return letter


def validate_filename(value: str):
    real_value = ""
    for letter in value:
        real_value += replace_bad_character(letter)
    return real_value


def get_player_info(player_str):
    player_info = player_str.split("-")
    return player_info[0].strip(), player_info[1].strip()


def get_latest_image():
    ftp = ftplib.FTP()
    ftp.connect(config["ip"], 5000)
    ftp.login()
    directory_to_grab = "/Nintendo/Album/"
    dirs = ftp.nlst(directory_to_grab)
    years = []
    for dir in dirs:
        number = dir.split("/")
        years.append(number[-1])
    years.sort()
    years.reverse()
    directory_to_grab += years[0] + "/"
    dirs = ftp.nlst(directory_to_grab)
    months = []
    for dir in dirs:
        number = dir.split("/")
        months.append(number[-1])
    months.sort()
    months.reverse()
    directory_to_grab += months[0] + "/"
    dirs = ftp.nlst(directory_to_grab)
    days = []
    for dir in dirs:
        number = dir.split("/")
        days.append(number[-1])
    days.sort()
    days.reverse()
    directory_to_grab += days[0] + "/"
    entries = list(ftp.mlsd(directory_to_grab))
    entries.sort(key=lambda entry: entry[1]["modify"], reverse=True)
    latest_name = entries[0][0]
    filename = directory_to_grab + latest_name
    image = io.BytesIO(b"")
    ftp.retrbinary("RETR " + filename, image.write)
    image.seek(0)
    return image


async def execute(controller_state, script_path):
    script_runner = ScriptRunner(controller_state)
    script_runner.is_looping = False
    script_file_name = os.path.expanduser(script_path)
    if os.path.exists(script_file_name):
        await script_runner.execute_script_file(script_file_name)
    else:
        print("not found")


async def load_match(controller_state, game_start, fp1_tag, fp2_tag):
    if game_start == True:
        await execute(controller_state, "tournament-scripts/start_game")
        s.connect((ip, int(port)))
        await asyncio.sleep(18)
        await execute(controller_state, "tournament-scripts/smash_menu")
    else:
        await execute(controller_state, "tournament-scripts/smash_menu_after_match")
    await execute(controller_state, "tournament-scripts/load_fp1")
    controller_state.set_nfc(fp1_tag)
    await asyncio.sleep(5)
    controller_state.set_nfc(None)
    await execute(controller_state, "tournament-scripts/load_fp2")
    controller_state.set_nfc(fp2_tag)
    await asyncio.sleep(5)
    controller_state.set_nfc(None)
    await execute(controller_state, "tournament-scripts/start_match")


def match_sorting_helper(sort_key, match):
    if sort_key == 'round':
        if (match[sort_key] < 0):
            return abs(match[sort_key]) + 0.5  # Make losers round positive, with a partial increase so it's after the same winners round, but before the next

    return match[sort_key]

def is_in_blacklist(match, blacklist):
    if blacklist == None:
        return False

    match_num = match["suggested_play_order"]
    round_num = match["round"]

    if match_num in blacklist["matches"]["no_group"]:
        return True
    if round_num in blacklist["rounds"]:
        return True
    return False

def get_runnable_matches(tour: Tournament):
    matches = [match for match in tour.matches if match["state"] == "open"]
    blacklist = None
    if os.path.exists("./blacklist.json"):
        with open("./blacklist.json") as fp:
            blacklist = json.load(fp)

    matches = [match for match in matches if not is_in_blacklist(match, blacklist)]

    if os.path.exists("./order.json"):
        with open("./order.json") as fp:
            order = json.load(fp)
    else:
        order = ["round", "suggested_play_order"]
    matches.sort(key=(lambda match: ([match_sorting_helper(sort_key, match) for sort_key in order])))
    return matches


def get_next_match(tour: Tournament):
    tour.refresh_matches()
    matches = get_runnable_matches(tour)
    if len(matches) == 0 :
        return None
    return matches[0]


async def handle_tournament_closure(tour, controller_state):
    tour.end()
    print()
    await execute(controller_state, "tournament-scripts/exit_to_home_and_close_game")
    print("Tournament Finished")


async def main(tour: Tournament):
    global bindict
    webhook_list = []
    for urls in config["webhook_url"]:
        webhook_list.append(
            webhook.MatchResultWebhoook(
                urls["url"], config["webhook_name"], urls["thread_id"], config["webhook_avatar_url"]
            )
        )

    # the type of controller to create
    controller = Controller.PRO_CONTROLLER  # or JOYCON_L or JOYCON_R
    # a callback to create the corresponding protocol once a connection is established
    factory = controller_protocol_factory(controller)
    # start the emulated controller
    transport, protocol = await create_hid_server(factory, reconnect_bt_addr="auto")
    # get a reference to the state being emulated.
    controller_state: ControllerState = protocol.get_controller_state()
    # wait for input to be accepted
    await controller_state.connect()
    entries = []
    with open("entries.tsv") as fp:
        # open the entry tsv submissionapp provides
        entry_tsv = csv.reader(fp, delimiter="\t")
        next(entry_tsv)
        for entry in entry_tsv:
            amiibo_name = entry[0]
            character_name = entry[1]
            trainer_name = entry[2]

            name_for_bracket = f"{trainer_name} - {character_name}"
            # This variable is the "full name" of sorts,
            # just has the amiibo's name appended to the end of it
            full_name = f"{name_for_bracket} - {amiibo_name}"

            # Since duplicates are possible, and we can't have duplicate dictionary keys,
            # we do a while loop to effectively eliminate all of those
            while name_for_bracket in bindict:
                # Get the first duplicate amiibo by it's full name, and then remove the trainer - character name
                # from the dictionary
                first_amiibo = bindict[name_for_bracket]
                bindict.pop(name_for_bracket)

                # After that, we re append the first duplicate amiibo with their full name to the dictionary
                bindict[first_amiibo["full_name"]] = first_amiibo

                # Once we finish that, we set their bracket name to their full name
                name_for_bracket = full_name
            entries.append(name_for_bracket)

            # After we finish handling duplicate amiibo, we save the amiibo to the trainer dictionary
            bindict[name_for_bracket] = {
                "full_name": full_name,
                "file_path": validate_filename(
                    f"{trainer_name.rstrip()}-{character_name}-{amiibo_name}"
                ),
            }

    print("Finished parsing Submissionapp TSV")
    # If the tournament has not started yet, add the amiibo and start it
    if tour.tournament["state"] == "pending":
        for entry in entries:
            tour.add_participant(entry)
        tour.shuffle_participants()
        tour.start()

    # The variable that controls if the game has started
    # We set it to true on first load
    game_start = True


    while True:
        match = get_next_match(tour)
        if match == None:
            await handle_tournament_closure(tour, controller_state)
            break
        try:
            p1 = tour.get_user_from_id(match["player1_id"])
            p2 = tour.get_user_from_id(match["player2_id"])
            name_to_id = {p1: match["player1_id"], p2: match["player2_id"]}
            p1_filepath = bindict[p1]["file_path"]
            p2_filepath = bindict[p2]["file_path"]
            tour.mark_in_progress(match["id"])
            with open(os.path.join("tourbins", p1_filepath + ".bin"), "rb") as fp1_file:
                fp1_hex = fp1_file.read()

            with open(os.path.join("tourbins", p2_filepath + ".bin"), "rb") as fp2_file:
                fp2_hex = fp2_file.read()
            fp1_tag = NFCTag(data=fp1_hex, source=p1_filepath, mutable=True)
            fp2_tag = NFCTag(data=fp2_hex, source=p2_filepath, mutable=True)
            await load_match(controller_state, game_start, fp1_tag, fp2_tag)
            game_start = False
            while True:
                data = s.recv(1024)
                if data.decode().startswith("[match_end] match_data_json: "):
                    data_json = json.loads(
                        data.decode()
                        .strip('[match_end] match_data_json: "')
                        .strip("\n")
                        .lstrip()
                        .replace("\\", "")
                        .rstrip('"')
                    )
                    print(data_json)
                    break
                if data.decode().startswith(
                    "[match_end] One of the fighters is not an amiibo, exiting."
                ):
                    await asyncio.sleep(4)
                    await restart_match(controller_state, fp1_tag, fp2_tag)
                    continue
            score = (
                str(data_json["fp1_info"]["score"])
                + "-"
                + str(data_json["fp2_info"]["score"])
            )
            print(score)
            p1_score = data_json["fp1_info"]["score"]
            p2_score = data_json["fp2_info"]["score"]
            if p1_score > p2_score:
                winner_str, loser_str = p1, p2
                winner_score, loser_score = p1_score, p2_score
            else:
                winner_str, loser_str = p2, p1
                winner_score, loser_score = p2_score, p1_score
            winner_name, winner_character = get_player_info(winner_str)
            loser_name, loser_character = get_player_info(loser_str)

            tour.set_score(match["id"], name_to_id[winner_str], score)
            match_data.export_result_to_csv(
                data_json,
                tour.get_tournament_name(),
                bindict[p1]["file_path"],
                bindict[p2]["file_path"],
            )
            await asyncio.sleep(5)
            await button_push(controller_state, "capture", sec=0.15)
            await execute(controller_state, "tournament-scripts/on_match_end")
            await execute(controller_state, "tournament-scripts/after_match")
            for webhooks in webhook_list:
                while True:
                    error = False
                    try:
                        await webhooks.send_result(
                            f"Running {tour.get_tournament_name()}.\n{winner_name}'s {winner_character} {winner_score}-{loser_score} {loser_name}'s {loser_character}",
                            get_latest_image(),
                        )
                    except ConnectionResetError:
                        error = True
                        pass
                    if error:
                        time.sleep(2)
                    else:
                        break
            await asyncio.sleep(5)
        except IndexError:
            break
    # wait for it to be sent at least once
    await controller_state.send()


if __name__ == "__main__":
    tour = Tournament(
        config["tour_url"], config["challonge_username"], config["challonge_api_key"]
    )

    if tour.tournament["state"] == "complete":
        config["tour_url"] = input("Input a new tournament's url: ")
        tour = Tournament(
            config["tour_url"], config["challonge_username"], config["challonge_api_key"]
        )
    log.configure(console_level=logging.ERROR)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(tour))
