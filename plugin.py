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
import pytz

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

    def set(self, irc, msg, args, timezone):
        """<timezone>
        Sets location for your current ident@host to <timezone>
        for eg. America/Chicago
        """
        nick = msg.nick
        if nick in self.db:
            self.db[nick]['timezone'] = timezone
        else:
            self.db[nick] = {'timezone': timezone }
        irc.replySuccess()
    set = wrap(set, ["something"])

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
            method = 'Undefined'

        nick = msg.nick
        if nick in self.db:
            timezone = self.db[nick].get('timezone', 'UTC')
            tz = pytz.timezone(timezone)
            time = datetime.datetime.now(tz=tz)
            dose_td = 0
            if ago is not None and len(ago) == 4:
                dose_td = datetime.timedelta(hours=int(ago[0:2]), minutes=int(ago[2:4]))
                dose_td_s = dose_td.total_seconds()
                time = time - dose_td
            doseLog = {'time': time, 'dose': dose, 'drug': name, 'method': method }
            doses = self.db[nick].get('doses')
            if doses:
                doses.append(doseLog)
            else:
                doses = [doseLog]
            self.db[nick]['doses'] = doses
        else:
            timezone = 'UTC'
            tz = pytz.timezone(timezone)
            time = datetime.datetime.now(tz=tz)
            dose_td = 0
            if ago is not None and len(ago) == 4:
                dose_td = datetime.timedelta(hours=int(ago[0:2]), minutes=int(ago[2:4]))
                dose_td_s = dose_td.total_seconds()
                time = time - dose_td
            doseLog = {'time': time, 'dose': dose, 'drug': name, 'method': method }
            doses = [doseLog]
            self.db[nick] = {'timezone': timezone, 'doses': doses}

        if dose_td == 0:
            re = utils.str.format("You dosed %s of %s at %t, %s", dose, drug_and_method, time.timetuple(), timezone)
            if onset is not None:
                re += utils.str.format(". You should start feeling effects %s from now", onset)
        else:
            re = utils.str.format("You dosed %s of %s at %t, %s ; %T ago", dose, drug_and_method, time.timetuple(), timezone, dose_td.total_seconds())
            if onset is not None:
                re += utils.str.format(". You should have/will start feeling effects %s from/after dosing", onset)
        irc.reply(re)

    @wrap([optional('positiveInt')])
    def lastdose(self, irc, msg, args, history):
        """<n>

        retrieves your <n>th last logged dose
        """
        nick = msg.nick
        if nick in self.db:
            if history:
                hist = -int(history)
                lastdose = self.db[nick]['doses'][-int(history)]
            else:
                lastdose = self.db[nick]['doses'][-1]
            dose = lastdose['dose']
            drug = lastdose['drug']
            dose_time = lastdose['time']
            timezone = self.db[nick]['timezone']
            tz = pytz.timezone(timezone)
            time = datetime.datetime.now(tz=tz)
            since_dose = time - dose_time
            since_dose_seconds = since_dose.total_seconds()
            if history:
                re = utils.str.format("Your %i'th last dose was %s of %s at %t %s, %T ago", history, dose, drug, dose_time.timetuple(), timezone, since_dose_seconds)
            else:
                re = utils.str.format("You last dosed %s of %s at %t %s, %T ago", dose, drug, dose_time.timetuple(), timezone, since_dose_seconds)
            irc.reply(re)
        else:
            irc.error(f'No doses saved for {nick}')







Class = Tripsit


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

