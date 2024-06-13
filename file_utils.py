import ftplib
import os
import io

def get_latest_image(ip):
    ftp = ftplib.FTP()
    ftp.connect(ip, 5000)
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

def replace_bad_character(letter):
    if letter in "%:/\"\\[]<>*?|":
        return "+"
    else:
        return letter


def validate_filename(value: str):
    real_value = ""
    for letter in value:
        real_value += replace_bad_character(letter)
    return real_value

def find_bins_in_folder(entry_tsv):
    for entry in entry_tsv:
        amiibo_name = entry[0]
        character_name = entry[1]
        trainer_name: str= entry[2].strip() # thanks amiibo trainers for adding white space to your submissions

        filename = validate_filename(
                    f"{trainer_name.replace("_", " ").rstrip()}-{character_name}-{amiibo_name}.bin"
                )

        if filename in os.listdir("./tourbins"):
            continue
        else:
            print(f"{trainer_name}'s {character_name} could not be found!")