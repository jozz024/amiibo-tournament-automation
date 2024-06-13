import os
import json

class Config:
    def __init__(self):
        if not os.path.exists("./config.json"):
            self._config: dict = {}
            self._config["tour_url"]       = input("Input the challonge tournament url extension: ")
            self._config["ip"]             = input("Input your Nintendo Switch's IP address: ")
            self._config["thread_data"]    = {"url": input("Input the url of your webhook: "), "id": input("Input the ID of the thread you will be putting results in: ")}
            self._config["webhook_data"]   = {"name": input("Input the name your webhook will use: "), "image": input("Input the link to the image you want the bot to use" )}
            self._config["challonge_data"] = {"name": input("Input your challonge username: "), "api_key": input("Input your challonge API Key")}
            with open("config.json", "w+") as cfg:
                json.dump(self._config, cfg, indent=4)
        else:
            with open("config.json") as cfg:
                self._config: dict = json.load(cfg)
        self.tour_url       = self._config["tour_url"]
        self.ip             = self._config["ip"]
        self.thread_data    = self._config["thread_data"]
        self.webhook_data   = self._config["webhook_data"]
        self.challonge_data = self._config["challonge_data"]