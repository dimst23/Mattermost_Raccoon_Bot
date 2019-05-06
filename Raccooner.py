#!/usr/bin/env python3

import asyncio
import json
import threading
import time
from datetime import datetime
import requests
import yaml
from mattermostdriver import Driver


class Raccooner:
    def __init__(self):
        with open('settings.yaml', "r") as file:
            self.parsed_data = yaml.safe_load(file)

        self.matt = Driver({
                'url': self.parsed_data["Raccooner"]["mattermost"]["general"]["url"],
                'token': self.parsed_data["Raccooner"]["mattermost"]["general"]["access_token"],
                'port': self.parsed_data["Raccooner"]["mattermost"]["general"]["port"],
                'debug': False
        })
        self.matt.login()  # Automatic login
        self.raccoon_stats = {}  # Create an empty dictionary

    @asyncio.coroutine
    def event_handler(self, message):
        msg = json.loads(message)  # Parse the reported event

        try:
            event_type = msg["event"]

            # Try to parse the message as a post
            if event_type == "reaction_added" or event_type == "reaction_removed":
                reaction = json.loads(msg["data"]["reaction"])  # Parse reaction data
                if reaction["emoji_name"] == "raccoon":
                    if event_type == "reaction_removed":
                        count = self.raccoon_stats[reaction["post_id"]]["raccoon_count"]
                        self.raccoon_stats[reaction["post_id"]]["raccoon_count"] = count - 1
                    else:
                        if not self.raccoon_stats[reaction["post_id"]]["reaction_time"]:
                            self.raccoon_stats[reaction["post_id"]]["reaction_time"] = reaction["create_at"]
                        count = self.raccoon_stats[reaction["post_id"]]["raccoon_count"]
                        self.raccoon_stats[reaction["post_id"]]["raccoon_count"] = count + 1

            else:
                post = json.loads(msg["data"]["post"])
                excluded_channel = bool(msg["data"]["channel_name"] not in
                                        self.parsed_data["Raccooner"]["mattermost"]["general"]["excluded_channels"])

                if event_type == "posted" and msg["data"]["channel_type"] == "O" and not post["hashtags"] and not \
                        post["root_id"] and excluded_channel:
                    rac_url = "https://" + MM_URL + "/" + self.matt.teams.get_team(msg["data"]["team_id"])["name"] + \
                              "/pl/" + post["id"]
                    requests.post(self.parsed_data["Raccooner"]["mattermost"]["bot_specific"]["hook_url"], json={
                        "channel":  self.parsed_data["Raccooner"]["mattermost"]["bot_specific"]["channel"],
                        "username": self.parsed_data["Raccooner"]["mattermost"]["bot_specific"]["username"],
                        "icon_url": self.parsed_data["Raccooner"]["mattermost"]["bot_specific"]["icon"],
                        "text": "**#RaccoonsInAction**\n# Raccoon Squad Time for Action!!\n%s" % rac_url
                    })
                    self.raccoon_stats.update({
                            post["id"]: {
                                    "post_time": post["create_at"],
                                    "reaction_time": 0,
                                    "permalink": rac_url,
                                    "deleted": False,
                                    "raccoon_count": 0
                            }
                    })
                elif event_type == "post_deleted":
                    self.raccoon_stats[post["id"]]["deleted"] = True
        except KeyError:
            pass

    def report_statistics(self):
        core_string = ""
        stat_string = ""
        total_raccoons = 0
        counter = 1

        utc = time.gmtime()
        delta_utc_decimal = int((self.parsed_data["Raccooner"]["mattermost"]["bot_specific"]["utc_update_time"] -
                                 utc.tm_hour + utc.tm_min/60.0 + utc.tm_sec/3600.0) * 3600)
        if delta_utc_decimal < 0:
            delta_utc_decimal = 86400 - delta_utc_decimal  # Remove the elapsed seconds
        try:
            for post in self.raccoon_stats.keys():
                if counter == 1:
                    date = datetime.utcfromtimestamp(self.raccoon_stats[post]["post_time"]/1000).strftime('%d/%m/%Y')
                    stat_string = "**#RaccooningStats**\nRaccoon Statistics for {}\n\n".format(date)
                if not self.raccoon_stats[post]["deleted"]:
                    if bool(self.raccoon_stats[post]["reaction_time"] != 0):
                        delta_t = (self.raccoon_stats[post]["reaction_time"] - self.raccoon_stats[post][
                            "post_time"])/1000.0
                        if int(delta_t) < 60:
                            delta_t = "{} seconds".format(round(delta_t))
                        else:
                            delta_t = "{} minutes".format(round(delta_t/60.0, 2))
                    else:
                        delta_t = "_Missed_"
                    core_string = core_string + "[**Post {}**]({})\n".format(counter,
                                                                             self.raccoon_stats[post]["permalink"])
                    core_string = core_string + "* Reaction time: {}\n" \
                                                "* Raccoons born: {}\n".format(delta_t,
                                                                               self.raccoon_stats[post]["raccoon_count"]
                                                                               )
                    total_raccoons = total_raccoons + self.raccoon_stats[post]["raccoon_count"]
                counter = counter + 1

            # Send the statistics
            if core_string:
                stat_string = stat_string + "Total raccoons born: {}\n" \
                                            "Total raccoon families: {}\n\n".format(total_raccoons, counter) + \
                              core_string
                requests.post(self.parsed_data["Raccooner"]["mattermost"]["bot_specific"]["hook_url"], json={
                        "channel":  self.parsed_data["Raccooner"]["mattermost"]["bot_specific"]["channel"],
                        "username": self.parsed_data["Raccooner"]["mattermost"]["bot_specific"]["username"],
                        "icon_url": self.parsed_data["Raccooner"]["mattermost"]["bot_specific"]["icon"],
                        "text": stat_string
                })
        except KeyError:
            pass
        self.raccoon_stats = {}  # Reset the statistics dictionary
        threading.Timer(delta_utc_decimal, self.report_statistics).start()

    def run(self):
        self.report_statistics()  # Start the statistics thread
        self.matt.init_websocket(self.event_handler)


if __name__ == "__main__":
    rac = Raccooner()
    rac.run()
