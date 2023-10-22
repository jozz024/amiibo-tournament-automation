import nextcord
from nextcord import File
import aiohttp

class Thread:
    def __init__(self, id):
        self.id = id

class MatchResultWebhoook:
    def __init__(self, url, name, thread_id, avatar_url= None) -> None:
        self.url = url
        self.name = name
        self.thread_id = thread_id
        self.avatar_url = avatar_url

    async def send_result(self, message, image):
        async with aiohttp.ClientSession() as session:
            self.webhook: nextcord.Webhook = nextcord.Webhook.from_url(url = self.url, session = session)
            if self.thread_id is not "None":
                thread = Thread(int(self.thread_id))
            else:
                thread = None
            if self.avatar_url is not None:
                await self.webhook.send(message, file=File(image, "unknown.jpeg"), username=self.name, thread=thread, avatar_url=self.avatar_url)
            else:
                await self.webhook.send(message, file=File(image, "unknown.jpeg"), username=self.name, thread=thread)