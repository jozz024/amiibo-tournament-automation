import nextcord
from nextcord import File
import aiohttp

class Thread:
    def __init__(self, id):
        self.id = id

class MatchResultWebhoook:
    def __init__(self, url, name, avatar_url= None) -> None:
        self.url = url
        self.name = name
        self.avatar_url = avatar_url

    async def send_result(self, message, image):
        async with aiohttp.ClientSession() as session:
            self.webhook: nextcord.Webhook = nextcord.Webhook.from_url(url = self.url, session = session)
            thread = Thread(id = 1143618186349125633)
            if self.avatar_url is not None:
                await self.webhook.send(message, file=File(image, "unknown.jpeg"), username=self.name, avatar_url=self.avatar_url, thread = thread)
            else:
                await self.webhook.send(message, file=File(image, "unknown.jpeg"), username=self.name, thread = thread)