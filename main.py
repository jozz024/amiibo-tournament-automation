from joycontrol.protocol import controller_protocol_factory
from joycontrol.server import create_hid_server
from joycontrol.controller import Controller
import logging
from joycontrol.controller_state import ControllerState
from joycontrol.controller_state import button_push
from joycontrol.ScriptRunner import ScriptRunner
from joycontrol import logging_default as log, utils
from joycontrol.nfc_tag import NFCTag
from tournament import Tournament
import os
import json
import socket
import io
import asyncio
from match_utils import *
import ftplib
import webhook
import config
from file_utils import *
import time
import match_data
import csv

conf = config.Config()
ip = conf["ip"]
port = "6969"
bin_dictionary = {} # Dictionary for storing bins connected to their challonge counterpart
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
socket_connected = False
previous_image: io.BytesIO = None

def get_player_info(player_str: str):
    player_info = player_str.split(" - ")
    return player_info[0], player_info[1]

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
        s.setblocking(False)
        await asyncio.sleep(18)
        await execute(controller_state, "tournament-scripts/smash_menu")
    else:
        await execute(controller_state, "tournament-scripts/smash_menu_after_match")
    await execute(controller_state, "tournament-scripts/load_fp1")
    controller_state.set_nfc(fp1_tag)
    await execute(controller_state, "tournament-scripts/load_fp2")
    controller_state.set_nfc(None)
    controller_state.set_nfc(fp2_tag)
    await asyncio.sleep(5)
    controller_state.set_nfc(None)
    await execute(controller_state, "tournament-scripts/start_match")

async def restart_match(controller_state, fp1_tag, fp2_tag):
    global s
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    await load_match(controller_state, True, fp1_tag, fp2_tag)

async def handle_tournament_closure(tour: Tournament, controller_state):
    await execute(controller_state, "tournament-scripts/exit_to_home_and_close_game")
    print()
    try:
        tour.end()
        print("Tournament Finished")
    except:
        print("Ran out of matches to do!")

async def send_results(webhook_list, tour: Tournament, winner_data, loser_data):
    if os.path.exists("./users.json"):
        with open("./users.json") as fp:
            users = json.load(fp)
        if winner_data["name"] in users:
            winner_data["name"] = f"<@!{users[winner_data['name']]}>"
        if loser_data["name"] in users:
            loser_data["name"] = f"<@!{users[loser_data['name']]}>"
    for webhooks in webhook_list:
        while True:
            error = False
            try:
                await webhooks.send_result(
                    f"Running {get_tournament_name(tour)}.\n{winner_data['name']}'s {winner_data['character']} {winner_data['score']}-{loser_data['score']} {loser_data['name']}'s {loser_data['character']}",
                    get_latest_image(),
                )
            except ConnectionResetError:
                error = True
                pass
            if error:
                time.sleep(2)
            else:
                break

async def main(tour: Tournament):
    global bin_dictionary
    webhook_list = []
    webhook_list.append(
        webhook.MatchResultWebhoook(
            conf.thread_data["url"], conf.webhook_data["name"], conf.thread_data["thread_id"], conf.webhook_data["image"]
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

    fp = open("entries.tsv")
    # open the entry tsv submissionapp provides
    entry_tsv = csv.reader(fp, delimiter="\t")
    next(entry_tsv)
    find_bins_in_folder(entry_tsv)
    
    fp.seek(0)
    next(entry_tsv)
    for entry in entry_tsv:
        amiibo_name = entry[0]
        character_name = entry[1]
        trainer_name = entry[2].strip() # thanks amiibo trainers for adding white space to your submissions

        name_for_bracket = f"{trainer_name} - {character_name}"
        # This variable is the "full name" of sorts,
        # just has the amiibo's name appended to the end of it
        full_name = f"{name_for_bracket} - {amiibo_name}"

        # Since duplicates are possible, and we can't have duplicate dictionary keys,
        # we do a while loop to effectively eliminate all of those
        while name_for_bracket in bin_dictionary:
            # Get the first duplicate amiibo by it's full name, and then remove the trainer - character name
            # from the dictionary
            first_amiibo = bin_dictionary[name_for_bracket]
            bin_dictionary.pop(name_for_bracket)

            # After that, we re append the first duplicate amiibo with their full name to the dictionary
            bin_dictionary[first_amiibo["full_name"]] = first_amiibo

            # Once we finish that, we set their bracket name to their full name
            name_for_bracket = full_name
        entries.append(name_for_bracket)

        # After we finish handling duplicate amiibo, we save the amiibo to the trainer dictionary
        bin_dictionary[name_for_bracket] = {
            "full_name": full_name,
            "file_path": validate_filename(
                f"{trainer_name.replace("_", " ").rstrip()}-{character_name}-{amiibo_name}.bin"
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
            p1 = get_user_from_id(tour, match["player1_id"])
            p2 = get_user_from_id(tour, match["player2_id"])
            name_to_id = {p1: match["player1_id"], p2: match["player2_id"]}
            p1_filepath = bin_dictionary[p1]["file_path"]
            p2_filepath = bin_dictionary[p2]["file_path"]
            mark_in_progress(tour, match["id"])
            with open(os.path.join("tourbins", p1_filepath), "rb") as fp1_file:
                fp1_hex = fp1_file.read()

            with open(os.path.join("tourbins", p2_filepath), "rb") as fp2_file:
                fp2_hex = fp2_file.read()
            fp1_tag = NFCTag(data=fp1_hex, source=p1_filepath, mutable=True)
            fp2_tag = NFCTag(data=fp2_hex, source=p2_filepath, mutable=True)
            await load_match(controller_state, game_start, fp1_tag, fp2_tag)
            game_start = False
            printed = False
            start_time = time.time()
            while True:
                try:
                    data = s.recv(1024)
                    if data.decode().startswith("[match_end] Started Set"):
                        printed = True
                    if data.decode().startswith("[match_end] match_data_json: "):
                        data_json = json.loads(
                            data.decode()
                            .strip('[match_end] match_data_json: "')
                            .strip("\n")
                            .lstrip()
                            .replace("\\", "")
                            .rstrip('"')
                        )
                        break
                    if "[match_end] One of the fighters is not an amiibo, exiting." in data.decode():
                        await asyncio.sleep(4)
                        await restart_match(controller_state, fp1_tag, fp2_tag)
                        continue
                except BlockingIOError:
                    pass
                now = time.time()

                if (now - start_time) > 15 and printed == False:
                    await asyncio.sleep(4)
                    await execute(controller_state, "tournament-scripts/exit_to_home_and_close_game")
                    await asyncio.sleep(4)
                    await restart_match(controller_state, fp1_tag, fp2_tag)
                    printed = False
                    start_time = time.time()
                    continue
            score = (
                str(data_json["fp1_info"]["score"])
                + "-"
                + str(data_json["fp2_info"]["score"])
            )
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

            set_score(tour, match["id"], name_to_id[winner_str], score)
            match_data.export_result_to_csv(
                data_json,
                get_tournament_name(tour),
                bin_dictionary[p1]["file_path"],
                bin_dictionary[p2]["file_path"],
            )
            await asyncio.sleep(5)
            await button_push(controller_state, "capture", sec=0.15)
            await asyncio.sleep(2)
            img: io.BytesIO = get_latest_image()
            if previous_image != None:
                while img.getvalue() == previous_image.getvalue():
                    await button_push(controller_state, "capture", sec=0.15)
                    await asyncio.sleep(2)
                    img: io.BytesIO = get_latest_image()
            await execute(controller_state, "tournament-scripts/on_match_end")
            await execute(controller_state, "tournament-scripts/after_match")
            winner_data = {"name": winner_name, "character": winner_character, "score": winner_score}
            loser_data = {"name": loser_name, "character": loser_character, "score": loser_score}
            await send_results(webhook_list, tour, winner_data, loser_data)
            await asyncio.sleep(5)
        except IndexError:
            break
    # wait for it to be sent at least once
    await controller_state.send()

if __name__ == "__main__":
    tour = Tournament(
        conf.tour_url, conf.challonge_data["name"], conf.challonge_data["api_key"]
    )

    if tour.tournament["state"] == "complete":
        conf.tour_url = input("Input a new tournament's url: ")
        tour = Tournament(
            conf.tour_url, conf.challonge_data["name"], conf.challonge_data["api_key"]
        )
    log.configure(console_level=logging.ERROR)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(tour))