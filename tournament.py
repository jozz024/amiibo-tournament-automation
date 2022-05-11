import challonge

class Tournament():
    def __init__(self, url, username, api_key) -> None:
        # Tell pychallonge about your [CHALLONGE! API credentials](http://api.challonge.com/v1).
        challonge.set_credentials(username, api_key)
        # Retrieve a tournament by its id (or its url).
        self.tournament = challonge.tournaments.show(url)
        self.matches = challonge.matches.index(self.tournament["id"])

    def get_all_participants(self):
        # Retrieve the participants for a given tournament.
        participants = challonge.participants.index(self.tournament["id"])

        return participants

    def add_participant(self, name):
        challonge.participants.create(self.tournament["id"], name)

    def refresh_matches(self):
        self.matches = challonge.matches.index(self.tournament["id"])

    def set_score(self, match_id, winner_id, score):
        challonge.matches.update(self.tournament["id"], match_id, scores_csv=score, winner_id=winner_id)

    def start(self):
        challonge.tournaments.start(self.tournament["id"])

    def reset(self):
        challonge.tournaments.reset(self.tournament["id"])

    def remove_all_participants(self):
        for participants in self.get_all_participants():
            challonge.participants.destroy(self.tournament["id"], participants["id"])

    def shuffle_participants(self):
        challonge.participants.randomize(self.tournament["id"])

    def get_user_from_id(self, id):
        return challonge.participants.show(self.tournament["id"], id)["name"]

    def get_user_from_group_player_id(self, id):
        users = challonge.participants.index(self.tournament["id"])
        for participants in users:
            if participants["group_player_ids"][0] == id:
                return participants["name"]

    def end(self):
        challonge.tournaments.finalize(self.tournament["id"])

    def mark_in_progress(self, match_id):
        challonge.matches.mark_as_underway(self.tournament["id"], match_id)

