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

if not os.path.exists("config.json"):
    config = {}
    config["ip"] = input("Input your switch's IP address.\n")
    config["webhook_url"] = input("Input the url of your webhook.\n")
    config["webhook_name"] = input("Input the preferred name of your webhook.\n")
    config["challonge_username"] = input("Please input your challonge username.\n")
    config["challonge_api_key"] = input("Please input your challonge api key.\n")

    with open("config.json", "w+") as cfg:
        json.dump(config, cfg)

with open("config.json") as cfg:
    config: dict = json.load(cfg)

ip = config["ip"]
port = "6969"
bindict = {}
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
socket_connected = False

async def restart_match(controller_state, fp1_tag, fp2_tag):
    global s
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    await load_match(controller_state, True, fp1_tag, fp2_tag)

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
    entries.sort(key = lambda entry: entry[1]['modify'], reverse = True)
    latest_name = entries[0][0]
    filename = directory_to_grab + latest_name
    image = io.BytesIO(b"")
    try:
        ftp.retrbinary("RETR " + filename, image.write)
    except ConnectionResetError:
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

async def main(tour: Tournament):
    global bindict

    webhk = webhook.MatchResultWebhoook()
    await webhk.set_webhook(config["webhook_url"], config["webhook_name"])

    # the type of controller to create
    controller = Controller.PRO_CONTROLLER # or JOYCON_L or JOYCON_R
    # a callback to create the corresponding protocol once a connection is established
    factory = controller_protocol_factory(controller)
    # start the emulated controller
    transport, protocol = await create_hid_server(factory, reconnect_bt_addr="auto")
    # get a reference to the state beeing emulated.
    controller_state: ControllerState = protocol.get_controller_state()
    # wait for input to be accepted
    await controller_state.connect()
    try:
        for files in os.listdir("./tourbins"):
            file = os.path.splitext(files)
            with open("character_names.txt") as chars:
                character_names = chars.readlines()
            for chars in character_names:
                chars = chars.strip("\n")
                lookfor = f"-{chars}-"
                if lookfor in file[0]:
                    user, amiibo_name = file[0].split(lookfor, 1)
                    name = f"{user} - {chars}"
            try:
                tour.add_participant(name)
            except:
                pass
            bindict[name] = file[0]
        try:
            tour.shuffle_participants()
            tour.start()
        except:
            pass
    except:
        pass
    new_match = True
    game_start = True
    match_num = 0
    while new_match == True:
        tour.refresh_matches()
        try:
            if tour.matches[match_num]["state"] == "complete":
                match_num += 1
            else:
                p1 = tour.get_user_from_id(tour.matches[match_num]["player1_id"])
                p2 = tour.get_user_from_id(tour.matches[match_num]["player2_id"])
                name_to_id = {
                    p1: tour.matches[match_num]["player1_id"],
                    p2: tour.matches[match_num]["player2_id"]
                }
                p1_filepath = bindict[p1]
                p2_filepath = bindict[p2]
                tour.mark_in_progress(tour.matches[match_num]["id"])
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
                    try:
                        if data.decode().startswith("[match_end] Player"):
                            w_l_str = data.decode().split(".")[1].lstrip()
                            break
                        if data.decode().startswith("[match_end] One of the fighters is not an amiibo, exiting."):
                            await restart_match(controller_state, fp1_tag, fp2_tag)
                            continue
                    except:
                        await restart_match(controller_state, fp1_tag, fp2_tag)
                        continue

                score = w_l_str
                print(score)
                p1_score, p2_score = score.replace("\n", "").split("-")
                if int(p1_score) > int(p2_score):
                    tour.set_score(tour.matches[match_num]["id"], name_to_id[p1], score)
                    winner = p1.split("-")
                    winner_name = winner[0].strip(" ")
                    winner_character = winner[1].strip(" ")
                    winner_score = p1_score.strip(" ")
                    loser_score = p2_score.strip(" ")
                    loser = p2.split("-")
                    loser_name = loser[0].strip(" ")
                    loser_character = loser[1].strip(" ")
                else:
                    tour.set_score(tour.matches[match_num]["id"], name_to_id[p2], score)
                    winner = p2.split("-")
                    winner_name = winner[0].strip(" ")
                    winner_character = winner[1].strip(" ")
                    winner_score = p2_score.strip(" ")
                    loser_score = p1_score.strip(" ")
                    loser = p1.split("-")
                    loser_name = loser[0].strip(" ")
                    loser_character = loser[1].strip(" ")
                await asyncio.sleep(5)
                await button_push(controller_state, "capture", sec=0.15)
                await execute(controller_state, "tournament-scripts/on_match_end")
                await execute(controller_state, "tournament-scripts/after_match")
                await webhk.send_result(f"{winner_name}'s {winner_character} {winner_score}-{loser_score} {loser_name}'s {loser_character}", get_latest_image())
                await asyncio.sleep(12)
                new_match = True
        except IndexError:
            tour.refresh_matches()
            tour.end()
            await execute(controller_state, "tournament-scripts/exit_to_home_and_close_game")
            new_match = False
    # wait for it to be sent at least once
    await controller_state.send()

if __name__ == "__main__":
    toururl = input("please input the url of the tournament:\n")
    tour = Tournament(toururl, config["challonge_username"], config["challonge_api_key"])
    log.configure(console_level=logging.ERROR)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(tour))

