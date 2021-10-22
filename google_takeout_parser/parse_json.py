"""
Lots of functions to transform the JSON from the Takeout to useful information
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Iterator, Any, Optional

from .time_utils import parse_datetime_millis
from .models import (
    Activity,
    LikedYoutubeVideo,
    HangoutsMessage,
    ChromeHistory,
    PlayStoreAppInstall,
    Location,
    Subtitles,
    Details,
    LocationInfo,
)
from .time_utils import parse_json_utc_date


# "YouTube and YouTube Music/history/search-history.json"
# "YouTube and YouTube Music/history/watch-history.json"
# This is also the 'My Activity' JSON format
def _parse_json_activity(p: Path) -> Iterator[Activity]:
    for blob in json.loads(p.read_text()):
        yield Activity(
            header=blob["header"],
            title=blob["title"],
            titleUrl=blob.get("titleUrl"),
            description=blob.get("description"),
            time=parse_json_utc_date(blob["time"]),
            subtitles=[
                Subtitles(s["name"], s.get("url")) for s in blob.get("subtitles", [])
            ],
            details=[Details(d["name"]) for d in blob.get("details", [])],
            locationInfos=[
                LocationInfo(
                    name=l.get("name"),
                    url=l.get("url"),
                    source=l.get("source"),
                    sourceUrl=l.get("sourceUrl"),
                )
                for l in blob.get("locationInfos", [])
            ],
            products=blob.get("products", []),
        )


def _parse_likes(p: Path) -> Iterator[LikedYoutubeVideo]:
    for jlike in json.loads(p.read_text()):
        yield LikedYoutubeVideo(
            title=jlike["snippet"]["title"],
            desc=jlike["snippet"]["description"],
            link="https://youtube.com/watch?v={}".format(
                jlike["contentDetails"]["videoId"]
            ),
            dt=parse_json_utc_date(jlike["snippet"]["publishedAt"]),
        )


def _parse_app_installs(p: Path) -> Iterator[PlayStoreAppInstall]:
    for japp in json.loads(p.read_text()):
        yield PlayStoreAppInstall(
            title=japp["install"]["doc"]["title"],
            device_name=japp["install"]["deviceAttribute"].get("deviceDisplayName"),
            dt=parse_json_utc_date(japp["install"]["firstInstallationTime"]),
        )


def _parse_location_history(p: Path) -> Iterator[Location]:
    ### HMMM, seems that all the locations are right after one another. broken? May just be all the location history that google has on me
    ### see numpy.diff(list(map(lambda yy: y.at, filter(lambda y: isinstance(Location), events()))))
    for japp in json.loads(p.read_text())["locations"]:
        yield Location(
            lng=float(japp["longitudeE7"]) / 1e7,
            lat=float(japp["latitudeE7"]) / 1e7,
            dt=parse_datetime_millis(japp["timestampMs"]),
        )


# Note: not used
def _parse_hangouts(p: Path) -> Iterator[Any]:
    for item in json.loads(p.read_text())["conversations"]:
        for event in item["events"]:
            if "chat_message" in event and "message_content" in event["chat_message"]:

                ts_naive = datetime.fromtimestamp(int(event["timestamp"]) / 1e6)
                ts = ts_naive.replace(tzinfo=timezone.utc)

                msg: Optional[str] = None
                link: Optional[str] = None
                chat_msg = event["chat_message"]
                msg_content = chat_msg["message_content"]
                if "segment" in msg_content:
                    for sc in msg_content["segment"]:
                        if sc["type"] == "TEXT":
                            msg = sc["text"]
                        elif sc["type"] == "LINK":
                            if "link_data" in sc:
                                link = sc["link_data"].get("link_target")
                    yield HangoutsMessage(text=msg, link=link, dt=ts)


def _parse_chrome_history(p: Path) -> Iterator[ChromeHistory]:
    for item in json.loads(p.read_text())["Browser History"]:
        time_naive = datetime.utcfromtimestamp(item["time_usec"] / 10 ** 6)
        yield ChromeHistory(
            title=item["title"],
            url=item["url"],
            dt=time_naive.replace(tzinfo=timezone.utc),
        )