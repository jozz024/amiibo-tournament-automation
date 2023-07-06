import nextcord
from nextcord import File
import aiohttp

class MatchResultWebhoook:
    def __init__(self, url, name, avatar_url: str | None = None) -> None:
        self.url = url
        self.name = name
        self.avatar_url = avatar_url

    async def send_result(self, message, image):
        async with aiohttp.ClientSession() as session:
            self.webhook: nextcord.Webhook = nextcord.Webhook.from_url(url = self.url, session = session)
            if self.avatar_url is not None:
                await self.webhook.send(message, file=File(image, "unknown.jpeg"), username=self.name, avatar_url=self.avatar_url)
            else:
                await self.webhook.send(message, file=File(image, "unknown.jpeg"), username=self.name)