from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands, ui
from discord.utils import format_dt

from functions import  check_time_more_than, str_to_timedelta
from datetime import datetime, timedelta, UTC
import aiohttp
import asyncio
from json import loads as json_loads

from dotenv import load_dotenv
import os
load_dotenv()

from typing import TYPE_CHECKING, Any, Literal, NamedTuple
if TYPE_CHECKING:
    from main import SHBot

EXPERTS_ROLE_ID = int(os.getenv("EXPERTS_ROLE_ID"))
MODERATORS_ROLE_ID = int(os.getenv("MODERATORS_ROLE_ID"))
DEVELOPERS_ROLE_ID = int(os.getenv("DEVELOPERS_ROLE_ID"))
ALERTS_THREAD_ID = int(os.getenv('ALERTS_THREAD_ID'))


class Cluster(NamedTuple):
    number: int
    ping: int
    online: bool

class StatusPage:
    """
    This helps to track clusters.

    Attributes
    -----------
    threshold: :class:`timedelta`
        How long a cluster has to be offline for in order for the notification message to be sent in the experts-channel.
    started_at: :class:`int`
        The timestamp in UTC of when a cluster was first detected offline.
    log_msgs: :class:`list`
        The msgs that had clusters logged as offline.
    notified_message: :class:`discord.Message`
        The message that was sent in the experts-channel when the threshold was hit.
    offline: :class:`int`
        The number of clusters currently offline.
    """

    __slots__ = ('threshold', 'started_at', 'notified_message',
                 'clusters', 'dashboard_online', 'cb_online', 'received_at')

    def __init__(self, threshold: timedelta):
        self.threshold = threshold
        self.started_at: int = 0

        self.notified_message: discord.Message | None = None

        self.clusters: list[Cluster] = []

        self.dashboard_online: bool = True
        self.cb_online: bool = True

        self.received_at: datetime = datetime.now(UTC)

    def __bool__(self):
        return bool(self.clusters)


    def hit_threshold(self) -> bool:
        """
        Whether a outage/cluster being offline is longer than the :attr:`threshold` set.
        """
        if self.started_at == 0:
            # Not enabled
            return False

        return check_time_more_than(self.started_at, self.threshold)


    @property
    def offline_clusters(self) -> list[Cluster]:
        """
        Returns the number of offline clusters
        """
        return [cluster for cluster in self.clusters if not cluster.online]


    @staticmethod
    def sort_clusters(clusters: list[Cluster], *, highest_ping: bool) -> list[Cluster]:
        """
        Sorts a COPY  of the clusters
        """

        if highest_ping:
            key = lambda cluster: -cluster.ping
        else:
            key = lambda cluster: cluster.ping

        return sorted(clusters, key=key)


    def get_slowest_clusters(self) -> tuple[Cluster, ...]:
        """
        Return a tuple of the top 5 slowest clusters
        """
        clusters = self.sort_clusters(self.clusters, highest_ping=True)
        return clusters[0], clusters[1], clusters[2], clusters[3], clusters[4]


    def update_from_ws_data(self, payload: list[dict[str, Any]]) -> int:
        """
        Updates state and returns the no. of offline clusters
        """
        clusters_payload = payload[0]['clusters']
        cb_payload = payload[1]
        dashboard_payload = payload[2]

        self.clusters.clear()

        offline: int = 0
        for i, cluster in enumerate(clusters_payload, start=1):
            is_online = cluster['state'] == "online"

            if not is_online:
                offline += 1
                if self.started_at == 0:
                    self.started_at = int(datetime.now(UTC).timestamp())

            self.clusters.append(Cluster(number=i, ping=cluster['ping'], 
                                         online=is_online))

        self.cb_online = cb_payload['smallBar']['text'] == "Operational"
        self.dashboard_online = dashboard_payload['smallBar']['text'] == "Operational"
        self.received_at = datetime.now(UTC)

        return offline

    def reset_state(self):
        """
        Resets `started_at` and `notified_message`
        """
        self.started_at = 0
        self.notified_message = None

    def clear(self):
        self.started_at = 0
        self.received_at = datetime.now(UTC)
        self.clusters.clear()
        self.cb_online = True
        self.dashboard_online = True
        self.notified_message = None


class Websocket:
    STATUS_WS_URL = "wss://user-ws.sapph.xyz/socket.io/?EIO=4&transport=websocket"

    """
    Handles the connection to websocket at sapph.xyz
    """

    __slots__= ('cog', '_connected', '_ws', '_task')

    def __init__(self, cog: ClusterTracker) -> None:
        self.cog = cog

        self._connected = asyncio.Event()
        self._ws = None
        self._task: asyncio.Task | None = None

    @property
    def connected(self):
        return self._connected.is_set()

    def start_connection(self) -> None:
        """
        Cancels previously running _task, and creates a new one.
        """
        if self._task is not None:
            self._task.cancel()

        self._task = asyncio.create_task(self.connect_to_ws())

    async def disconnect_ws(self):
        if self._ws is not None:
            await self._ws.close()
            self._ws = None

        if self._task is not None:
            self._task.cancel()

            try:
                await self._task
            except asyncio.CancelledError:
                pass

            self._task = None

    async def connect_to_ws(self):
        delay = 1 # delay for exponential backoff
        
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    async with session.ws_connect(self.STATUS_WS_URL) as ws:
                        self._ws = ws
                        self._connected.set()
                        delay = 1

                        await self.cog.receive_ws(ws)

                except asyncio.CancelledError:
                    raise

                except Exception as e:
                    await self.cog.bot.send_unhandled_error(e)

                finally:
                    self._ws = None
                    self._connected.clear()

                if delay >= 4:
                    await self.cog.bot.send_log(ALERTS_THREAD_ID, content=f"Reconnecting (sapph.xyz websocket) in `{delay}s`...")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 45)


class ClusterTracker(commands.Cog):
    def __init__(self, bot: SHBot) -> None:
        self.bot = bot
        self.cluster_tracker = StatusPage(timedelta(minutes=16))

        self.websocket = Websocket(self)

    async def cog_load(self) -> None:
        self.websocket.start_connection()

    async def cog_unload(self) -> None:
        await self.websocket.disconnect_ws()

    async def receive_ws(self, ws: aiohttp.ClientWebSocketResponse):
        """
        Called in :meth:`Websocket.connect_to_ws`
        """
        async for msg in ws:
            if msg.type != aiohttp.WSMsgType.TEXT:
                continue

            data: str = msg.data

            if data == "2":
                await ws.send_str("3")

            elif data.startswith("0"):
                await ws.send_str("40/status,")

            elif data.startswith("40/status"):
                await ws.send_str(
                    '42/status,1["get-guilds"]'
                )

            elif data.startswith("42/status,"):
                payload = json_loads(data.removeprefix("42/status,"))
                if len(payload) < 2:
                    return

                event = payload[0]
                actual_data = payload[1]

                if event == "status":
                    offline = self.cluster_tracker.update_from_ws_data(actual_data)
                    await self.handle_offline_clusters(offline)

    @staticmethod
    def format_timedelta(td: timedelta) -> str:
        hours = td.seconds // 3600 # (60s - 1m, 60m - 1h: 60 * 60 = 3600)
        if hours == 0:
            return f"{td.seconds / 60:.1f}min"

        remaining_mins = (td.seconds - (hours * 3600)) / 60
        return f"{hours}h, {remaining_mins:.1f}min"

    def get_expert_channel(self) -> discord.TextChannel | None:
        return discord.utils.get(self.bot.get_all_channels(), name="sapphire-experts") # type: ignore

    async def handle_offline_clusters(self,  offline: int) -> None:
        if offline == 0:
            # No clusters were detected offline
            notified_msg = self.cluster_tracker.notified_message
            if notified_msg is not None:
                experts_channel = self.get_expert_channel() or notified_msg.channel
                if experts_channel is None:
                    return

                lasted_for = datetime.now(UTC) - datetime.fromtimestamp(self.cluster_tracker.started_at, UTC)
                content = f"### All clusters are now online (Lasted `{self.format_timedelta(lasted_for)}`)"
                container = ui.Container(ui.TextDisplay(content), accent_color=discord.Color.green())
                reference = discord.MessageReference(message_id=notified_msg.id, channel_id=notified_msg.channel.id,
                                                     fail_if_not_exists=False)

                view = ui.LayoutView().add_item(container)
                await experts_channel.send(view=view, reference=reference)
            self.cluster_tracker.reset_state()
        else:
            if not self.cluster_tracker.hit_threshold() or self.cluster_tracker.notified_message is not None:
                return

            experts_channel = self.get_expert_channel()
            if experts_channel is None:
                return

            container = ui.Container(accent_color=discord.Colour.brand_red())
            header = f"## Clusters offline <t:{self.cluster_tracker.started_at}:R> ([STATUS](https://sapph.xyz/status))"
            container.add_item(ui.TextDisplay(header))
            container.add_item(ui.Separator())

            offline_clusters = self.cluster_tracker.offline_clusters
            clusters_offline_fmt = "\n".join(f"- Cluster **{cluster.number}**" for cluster in offline_clusters)
            container.add_item(ui.TextDisplay(f"*Currently offline **[{len(offline_clusters)}]**:*\n{clusters_offline_fmt}"))
            container.add_item(ui.Separator())
            container.add_item(ui.TextDisplay("-# Use `/cluster_tracker status` for live information."))

            self.cluster_tracker.notified_message = await experts_channel.send(view=ui.LayoutView().add_item(container))

    @staticmethod
    def format_online(online: bool) -> str:
        return '✅' if online else '❌'

    group_cmd = app_commands.Group(name="cluster_tracker", description="Commands related to cluster tracking")

    @group_cmd.command(name="status", description="Get live cluster information/status")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, DEVELOPERS_ROLE_ID, MODERATORS_ROLE_ID)
    @app_commands.describe(action="The action to execute, defaults to 'View'",
                           threshold="How long a cluster needs to be offline for, leave empty to not edit")
    async def cluster_tracking_status(self, interaction: discord.Interaction, action: Literal['View', 'Clear'] | None = None, threshold: str | None = None):
        await interaction.response.defer(ephemeral=True)

        if threshold is not None:
            try:
                td = str_to_timedelta(threshold)
            except ValueError:
                await interaction.followup.send(f"`{threshold}` is not a valid threshold!", ephemeral=True)
                return

            old_threshold = self.cluster_tracker.threshold
            self.cluster_tracker.threshold = td
            await interaction.followup.send(f"Successfully set threshold! (`{self.format_timedelta(old_threshold)}` -> `{threshold}`)",
                                            ephemeral=True)

        if not self.cluster_tracker:
            await interaction.followup.send("Cluster tracker data is empty!", ephemeral=True)
            return

        if action == 'Clear':
            self.cluster_tracker.clear()
            await interaction.followup.send("Successfully cleared!", ephemeral=True)
            return

     
        if action == 'View' or (action is None and threshold is None):
            offline_clusters = self.cluster_tracker.offline_clusters

            offline_container = ui.Container(ui.TextDisplay(f"## [Clusters Offline: {len(offline_clusters)}](https://sapph.xyz/status)"))
            if offline_clusters:
                colour = discord.Colour.brand_red()
                offline_container.add_item(ui.Separator())

                fmt = "\n".join(f"- Cluster **{cluster.number}**" for cluster in offline_clusters)
                content = f"Offline (<t:{self.cluster_tracker.started_at}:R>):\n{fmt}"
                offline_container.add_item(ui.TextDisplay(content))
            else:
                colour = discord.Colour.green()
            offline_container.accent_color = colour


            slowest_clusters = self.cluster_tracker.get_slowest_clusters()
            slow_container = ui.Container(ui.TextDisplay("### Top 5 slowest clusters"), ui.Separator())
            if slowest_clusters[0].ping >= 500:
                slow_container.accent_color = discord.Color.orange()
            fmt = "\n".join(f"- Cluster **{cluster.number}.** `{cluster.ping}ms`" for cluster in slowest_clusters)
            slow_container.add_item(ui.TextDisplay(fmt))


            db_cb_container = ui.Container(ui.TextDisplay("### Dashboard & CB"), ui.Separator())
            if not self.cluster_tracker.dashboard_online or not self.cluster_tracker.cb_online:
                db_cb_container.accent_colour = discord.Colour.brand_red()
            else:
                db_cb_container.accent_color = discord.Color.green()
            fmt = f"- Dashboard Online: {self.format_online(self.cluster_tracker.dashboard_online)}\n- CB Online: {self.format_online(self.cluster_tracker.cb_online)}"
            db_cb_container.add_item(ui.TextDisplay(fmt))


            info_container = ui.Container(ui.TextDisplay("### Debug & Info"), ui.Separator())
            info_description = (f"- Threshold: `{self.format_timedelta(self.cluster_tracker.threshold)}`"
                           f"\n- Last received: {format_dt(self.cluster_tracker.received_at, style='R')}")
            info_container.add_item(ui.TextDisplay(info_description))


            view = ui.LayoutView().add_item(offline_container).add_item(slow_container).add_item(db_cb_container).add_item(info_container)
            await interaction.followup.send(view=view, ephemeral=True)

    @staticmethod
    def get_cluster_numbers(text: str) -> set[int]:
        raw: list[str] = text.replace(" ", "").split(",")
        return {int(num) for num in raw}

    @group_cmd.command(name="search", description="Get information for specific clusters and more")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, DEVELOPERS_ROLE_ID, MODERATORS_ROLE_ID)
    @app_commands.describe(cluster_numbers="The cluster(s) to get info on. E.g: 10 | 12,54,21",
                           sort_by="The order to return in, defaults to ascending order. Shows 15 clusters if 'cluster_numbers' not provided")
    async def cluster_tracking_search(self, interaction: discord.Interaction, cluster_numbers: str | None = None,
                                         sort_by: Literal['highest_ping', 'lowest_ping'] | None = None):
        await interaction.response.defer(ephemeral=True)

        if cluster_numbers is not None:
            clusters: list[Cluster] = []

            try:
                numbers = self.get_cluster_numbers(cluster_numbers)
            except ValueError:
                await interaction.followup.send(f"`{cluster_numbers}` is not a valid cluster!", ephemeral=True)
                return

            for cluster_number in numbers:
                if len(self.cluster_tracker.clusters) < cluster_number or cluster_number < 1:
                    await interaction.followup.send(f"`{cluster_number}` is not a valid cluster!", ephemeral=True)
                    return
                
                cluster = self.cluster_tracker.clusters[cluster_number - 1]
                clusters.append(cluster)

            if len(clusters) == 1:
                await interaction.followup.send(f"- Cluster **{cluster.number}.** - `{cluster.ping}ms` | Online: {self.format_online(cluster.online)}",
                                                ephemeral=True)
                return
        else:
            clusters = self.cluster_tracker.clusters


        if sort_by == 'highest_ping':
            highest_ping = True
        elif sort_by == 'lowest_ping':
            highest_ping = False
        else:
            highest_ping = None

        if highest_ping is not None:
            clusters = self.cluster_tracker.sort_clusters(clusters, highest_ping=highest_ping)

        clusters = clusters[0:15]

        fmt = "\n".join([f"- Cluster **{cluster.number}.** - `{cluster.ping}ms` | Online: {self.format_online(cluster.online)}" \
                            for cluster in clusters])

        container = ui.Container()
        container.add_item(ui.TextDisplay(f"### {len(clusters)}/{len(self.cluster_tracker.clusters)} clusters"))
        container.add_item(ui.Separator())
        container.add_item(ui.TextDisplay(fmt))

        view = ui.LayoutView()
        view.add_item(container)
        await interaction.followup.send(view=view, ephemeral=True)


    @group_cmd.command(name="websocket", description="Get debug action/information on the websocket")
    @app_commands.checks.has_any_role(EXPERTS_ROLE_ID, DEVELOPERS_ROLE_ID, MODERATORS_ROLE_ID)
    @app_commands.describe(action="connect/disconnect/force_disconnect the ws, or view debug info")
    async def cluster_tracking_websocket(self, interaction: discord.Interaction, action: Literal['connect', 'disconnect', 'force_disconnect', 'view'] = 'view'):
        await interaction.response.defer(ephemeral=True)
        if action == 'view':
            content = f"- Is connected: `{self.websocket.connected}`\n- WS: {self.websocket._ws}"
            if self.websocket._task is not None:
                content += f"\n- Internal Task: `{self.websocket._task.done()}` (done) | `{self.websocket._task.cancelled()}` (cancelled)"
            else:
                content += f"\n- Internal Task: `None`"
            await interaction.followup.send(content=content, ephemeral=True)
            return

        if action == 'connect':
            if self.websocket.connected:
                await interaction.followup.send("Already connected!", ephemeral=True)
                return
            if self.websocket._task is not None and not self.websocket._task.done():
                await interaction.followup.send("WS not connected but `_task` is still running!", ephemeral=True)
                return
            self.websocket.start_connection()
            await interaction.followup.send("Successfully connected!", ephemeral=True)
        elif action == 'disconnect':           
            if not self.websocket.connected:
                await interaction.followup.send("Already disconnected (or the ws is currently sleeping, try again or `force_disconnect`)!",
                                                ephemeral=True)
                return

            if self.websocket._task is not None and self.websocket._task.done():
                await interaction.followup.send("WS connected but `_task` is stopped! Try `force_cancel`", ephemeral=True)
                return
            await self.websocket.disconnect_ws()
            await interaction.followup.send("Successfully disconnected!", ephemeral=True)
        else:
            await self.websocket.disconnect_ws()
            await interaction.followup.send("Successfully force disconnected the websocket!", ephemeral=True)


async def setup(bot: SHBot):
    await bot.add_cog(ClusterTracker(bot))