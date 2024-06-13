import os, csv

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

def find_discrepancy(bin_list: list[str], amiibo_spreadsheet):
    for entry in amiibo_spreadsheet:
            amiibo_name = entry[0]
            character_name = entry[1]
            trainer_name = entry[2].strip() # thanks amiibo trainers for adding white space to your submissions

            filename = validate_filename(f"{trainer_name}-{character_name}-{amiibo_name}.bin")

            if not filename in bin_list:
                # this doesnt account for if the amiibo has a bad name, but that shouldnt happen too often so we should be gucci
                trainer_name = trainer_name.replace("_", " ")

                real_filename = validate_filename(f"{trainer_name}-{character_name}-{amiibo_name}.bin")

                if not real_filename in bin_list:
                    continue
                else:
                    print(trainer_name)
                    idx = bin_list.index(real_filename)
                    bin_list.pop(idx)
                    bin_list.append(filename)
                    os.rename(f"tourbins/{real_filename}", f"tourbins/{filename}")

def main():
    with open("entries.tsv") as fp:
        # open the entry tsv submissionapp provides
        entry_tsv = csv.reader(fp, delimiter="\t")
        next(entry_tsv)
        find_discrepancy(os.listdir("tourbins"), entry_tsv)

if __name__ == "__main__":
    main()