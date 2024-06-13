from tournament import Tournament
import json
import requests
import os

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

def try_until_complete(func, *args, **kwargs):
    failed = True
    while failed:
        try:
            result = func(*args, **kwargs)
            failed = False
        except requests.exceptions.ConnectionError:
            failed = True
        except requests.exceptions.HTTPError:
            failed = True
    return result

def get_next_match(tour: Tournament):
    def refresh_matches_wrapper(tour: Tournament):
        tour.refresh_matches()

    try_until_complete(refresh_matches_wrapper, tour)
    matches = get_runnable_matches(tour)
    if len(matches) == 0 :
        return None
    return matches[0]

def set_score(tour: Tournament, match_id, winner_id, score):
    def set_score_wrapper(tour: Tournament, match_id, winner_id, score):
        tour.set_score(match_id, winner_id, score)
    try_until_complete(set_score_wrapper, tour, match_id, winner_id, score)

def get_tournament_name(tour: Tournament):
    def get_name_wrapper(tour: Tournament):
        return tour.get_tournament_name()
    name = try_until_complete(get_name_wrapper, tour)
    return name

def get_user_from_id(tour: Tournament, user_id):
    def get_user_wrapper(tour: Tournament, user_id):
        return tour.get_user_from_id(user_id)
    user = try_until_complete(get_user_wrapper, tour, user_id)
    return user

def mark_in_progress(tour: Tournament, match_id):
    def mark_wrapper(tour: Tournament, match_id):
        tour.mark_in_progress(match_id)
    try_until_complete(mark_wrapper, tour, match_id)
