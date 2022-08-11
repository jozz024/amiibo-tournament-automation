import nextcord
from nextcord import File
import aiohttp

class MatchResultWebhoook:
    def __init__(self, url, name) -> None:
        self.url = url
        self.name = name

    def send_result(self, message, image):
        self.webhook: nextcord.SyncWebhook = nextcord.SyncWebhook.from_url(url = self.url)
        self.webhook.send(message, file=File(image, "unknown.jpeg"), username=self.name)