import csv
import os

stage_translate_dict = {
    "battlefield": "Battlefield",
    "battlefield_s": "Small Battlefield",
    "end": "Final Destination",
    "ff_cave": "Northern Cave",
    "trail_castle": "Hollow Bastion"
}

def export_result_to_csv(result_data, tournament_name, fp1_name, fp2_name):
    file_path = f"{tournament_name}.csv"
    if not os.path.isfile(file_path):
        k = open(file_path, mode="x")
        k.close()
    file = open(file_path, "a")
    
    data = csv.writer(file, lineterminator="\n")

    max_index = len(result_data["stages_used"])
    for x in range(0, max_index):
        result = result_data["games_by_player"][x]
        p1_score = result_data['fp1_info']['score'] 
        p2_score = result_data['fp2_info']['score']
        winner = lambda fp1_name, result, fp2_name: fp1_name if result == 1 else fp2_name
        outcome = lambda p1_score, p2_score: f"{p1_score}:{p2_score}" if p1_score > p2_score else f"{p2_score}:{p1_score}"
        if x == max_index - 1:
            data.writerow([tournament_name, fp1_name, fp2_name, winner(fp1_name, result, fp2_name), outcome(p1_score, p2_score), result_data["stocks_taken"][x][0], result_data["stocks_taken"][x][1], stage_translate_dict[result_data["stages_used"][x]]])
        else:
            data.writerow([tournament_name, fp1_name, fp2_name, winner(fp1_name, result, fp2_name), "", result_data["stocks_taken"][x][0], result_data["stocks_taken"][x][1], stage_translate_dict[result_data["stages_used"][x]]])


# test_dict = {'fp1_info': {'score': 2}, 'fp2_info': {'score': 1}, 'games_by_player': [2, 1, 1], 'stages_used': ['battlefield', 'trail_castle', 'end'], 'stocks_taken': [[2, 3], [3, 1], [3, 2]]}

# export_result_to_csv(test_dict, "null", "a", "baller")

