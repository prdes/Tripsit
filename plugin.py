###
# Copyright (c) 2020, mogad0n
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

###

from supybot import utils, plugins, ircutils, callbacks, world, conf, log
from supybot.commands import *
import dateutil.parser
import json
import requests
import pickle
import sys
import datetime
import time
try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('Tripsit')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x: x

filename = conf.supybot.directories.data.dirize("Tripsit.db")


url_drug = "http://tripbot.tripsit.me/api/tripsit/getDrug"
url_combo = "http://tripbot.tripsit.me/api/tripsit/getInteraction"

insufflated = ["Insufflated", "Insufflated-IR", "Insufflated-XR"]

METHODS = {
    "iv": ["IV"],
    "shot": ["IV"],

    "im": ["IM"],

    "oral": ["Oral", "Oral-IR", "Oral-XR"],

    "insufflated": insufflated,
    "snorted": insufflated,

    "smoked": ["Smoked"]
}

class Tripsit(callbacks.Plugin):
    """Harm-Reduction tools from tripsit's tripbot and the tripsitwiki"""
    threaded = True

    def __init__(self, irc):
        self.__parent = super(Tripsit, self)
        self.__parent.__init__(irc)
        self.db = {}
        self._loadDb()
        world.flushers.append(self._flushDb)

    def _loadDb(self):
        """Loads the (flatfile) database mapping nicks to doses."""

        try:
            with open(filename, "rb") as f:
                self.db = pickle.load(f)
        except Exception as e:
            self.log.debug("Tripsit: Unable to load pickled database: %s", e)

    def _flushDb(self):
        """Flushes the (flatfile) database mapping nicks to doses."""

        try:
            with open(filename, "wb") as f:
                pickle.dump(self.db, f, 2)
        except Exception as e:
            self.log.warning("Tripsit: Unable to write pickled database: %s", e)

    def die(self):
        self._flushDb()
        world.flushers.remove(self._flushDb)
        self.__parent.die()

    @wrap(['something', optional('something')])
    def drug(self, irc, msg, args, name, category):
        """<drug> [<category>]
        fetches data on drug from tripsit wiki
        """
        category_list = []
        r = requests.get(url_drug, params={"name": name}).json()
        if not r['err']:
            drug = r["data"][0]["pretty_name"]
            properties = r["data"][0]["properties"]
            for key in properties:
                category_list.append(key)
            if category == None:
                re = drug + " Available categories are: " + ", ".join(category_list)
                irc.reply(re)
            else:
                if category in properties.keys():
                    re = drug + " " + properties[category]
                    irc.reply(re)
                else:
                    irc.error(f"Unknown category {drug} Available categories are: " + ", ".join(category_list))
        else:
            irc.error("unknown drug")

    def combo(self, irc, msg, args, drugA, drugB):
        """<drugA> <drugB>
        fetches known interactions between the substances provided.
        """
        r = requests.get(url_combo, params={f"drugA": drugA, f"drugB": drugB}).json()
        if not r["err"] and r["data"][0]:
            interaction = r["data"][0]
            drug_a = interaction["interactionCategoryA"]
            drug_b = interaction["interactionCategoryB"]
            interaction_status = interaction["status"]
            re = f"{drug_a} and {drug_b}: {interaction_status}"
            if 'note' in interaction:
                note = interaction["note"]
                re += f'. Note: {note}'
                irc.reply(re)
            else:
                irc.reply(re)
        else:
            irc.reply("Unknown combo (that doesn't mean it's safe). Known combos: lsd, mushrooms, dmt, mescaline, dox, nbomes, 2c-x, 2c-t-x, amt, 5-meo-xxt, cannabis, ketamine, mxe, dxm, pcp, nitrous, amphetamines, mdma, cocaine, caffeine, alcohol, ghb/gbl, opioids, tramadol, benzodiazepines, maois, ssris.")

    combo = wrap(combo, [("something"), ("something")])

    @wrap(["something", "something", optional("something"), optional("something")])
    def idose(self, irc, msg, args, dose, name, method, ago):
        """<amount> <drug> [<method>] [<ago>]
        <ago> is in the format HHMM
        logs a dose for you, use 'lastdose' command to retrieve
        """
        r = requests.get(url_drug, params={"name": name}).json()
        found_method = False
        onset = None
        if not r['err']:
            drug = r['data'][0]
            drug_name = drug['pretty_name']
            method_keys = ['value']
            methods = []
            if method:
                methods = [method.lower()]
                methods = METHODS.get(methods[0], methods)
                method_keys += methods

            if 'formatted_onset' in drug:
                match = list(set(method_keys)&
                    set(drug["formatted_onset"].keys()))
                if match:
                    onset = drug["formatted_onset"][match[0]]
                    found_method = True
                    if match[0] in methods:
                        method = (match or [method])[0]

                if onset and "_unit" in drug["formatted_onset"]:
                    onset = "%s %s" % (
                        onset, drug["formatted_onset"]["_unit"])
        drug_and_method = name
        if method:
            if not found_method:
                method = method.title()
            drug_and_method = "%s via %s" % (drug_and_method, method)
        else:
            method = 'Undefined/Probably boofed'



        time = datetime.datetime.utcnow()
        if not ago:
            self.db[msg.nick] = {'type': 'idose' ,'time': str(time), 'dose': dose, 'drug': name, 'method': method }
            re = f" You dosed {dose} of {drug_and_method} at {str(time)} UTC"
            if not onset == None:
                re += f". You should start feeling effects {onset} from now"
        else:
            hours = int(ago[0:2])
            minutes = int(ago[2:4])
            dose_td = datetime.timedelta(hours=hours, minutes=minutes)
            time_dosed = time - dose_td
            self.db[msg.nick] = {'type': 'hdose', 'time': str(time), 'time_dosed': str(time_dosed), 'dose': dose, 'drug': name, 'method': method }
            re = f" You dosed {dose} of {drug_and_method} at {str(time_dosed)} UTC, {str(hours)} hours and {str(minutes)} minutes ago"
            if not onset == None:
                re += f". You should have/will start feeling effects {onset} from {str(time_dosed)} UTC"
        irc.reply(re)


    def lastdose(self, irc, msg, args):
        """This command takes no arguments
        retrieves your last logged dose
        """
        if msg.nick in self.db:
            lastdose = self.db[msg.nick]
            time = datetime.datetime.utcnow()
            if lastdose['type'] == 'idose':
                dose_time = dateutil.parser.isoparse(lastdose['time'])
            elif lastdose['type'] == 'hdose':
                dose_time = dateutil.parser.isoparse(lastdose['time_dosed'])
            since_dose = time - dose_time
            since_dose_seconds = since_dose.total_seconds()
            since_dose_formatted = utils.str.format('%T', since_dose_seconds)
            re = f"You last dosed {lastdose['dose']} of {lastdose['drug'] }at {dose_time} UTC, {since_dose_formatted} ago"
            irc.reply(re)
        else:
            irc.error(f'No last dose saved for {msg.nick}')

    lastdose = wrap(lastdose)







Class = Tripsit


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
