import nextcord
from nextcord import File
import aiohttp

class MatchResultWebhoook:
    def __init__(self, url, name) -> None:
        self.url = url
        self.name = name

    async def send_result(self, message, image):
        async with aiohttp.ClientSession() as session:
            self.webhook: nextcord.Webhook = nextcord.Webhook.from_url(url = self.url, session = session)
            await self.webhook.send(message, file=File(image, "unknown.jpeg"), username=self.name)