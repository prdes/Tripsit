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

from supybot import utils, plugins, ircutils, callbacks
from supybot.commands import *
from pathlib import Path
from os import path
import dateutil.parser
import json
import requests
from datetime import datetime
try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('Tripsit')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x: x
dose_filename = 'dose.json'
dose_db = Path(dose_filename)
if not path.isfile(dose_filename):
    dose_db.write_text('{}')
dose_data = json.loads(dose_db.read_text())

URL_DRUG = "http://tripbot.tripsit.me/api/tripsit/getDrug"
URL_COMBO = "http://tripbot.tripsit.me/api/tripsit/getInteraction"
URL_WIKI = "http://drugs.tripsit.me/%s"

INSUFFLATED = ["Insufflated", "Insufflated-IR", "Insufflated-XR"]

METHODS = {
    "iv": ["IV"],
    "shot": ["IV"],

    "im": ["IM"],

    "oral": ["Oral", "Oral-IR", "Oral-XR"],

    "insufflated": INSUFFLATED,
    "snorted": INSUFFLATED,

    "smoked": ["Smoked"]
}

class Tripsit(callbacks.Plugin):
    """Harm-Reduction tools from tripsit's tripbot and the tripsitwiki"""
    threaded = True
    @wrap(['something', optional('something')])
    def drug(self, irc, msg, args, name, category):
        """<drug> [<category>]
        fetches data on drug from tripsit wiki
        """
        category_list = []
        r = requests.get(URL_DRUG, params={f"name": name}).json()
        # r = json.loads(utils.web.getUrlContent(URL_DRUG, data={f"name": name}))
        if not r['err']:
            drug = r["data"][0]["pretty_name"]
            properties = r["data"][0]["properties"]
            if category == None:
                # category_list = list(properties)
                for key in properties:
                    category_list.append(key)
                re = ", ".join(category_list)
                # re = category_list
                irc.reply(re)
            else:
                if category in properties.keys():
                    re = properties[category]
                    irc.reply(re)
                else:
                    irc.error("Unknown category")
        else:
            irc.error("unknown drug")

    def combo(self, irc, msg, args, drugA, drugB):
        """<drugA> <drugB>
        fetches known interaction between the substances provided.
        """
        r = requests.get(URL_COMBO, params={f"drugA": drugA, f"drugB": drugB}).json()
        if not r["err"] and r["data"][0]:
            interaction = r["data"][0]
            drug_a = interaction["interactionCategoryA"]
            drug_b = interaction["interactionCategoryB"]
            interaction_status = interaction["status"]
            note = interaction["note"]
            re = f"{drug_a} and {drug_b}: {interaction_status}, Note: {note}"
            irc.reply(re)
        else:
            irc.error("Unknown Combo")
    combo = wrap(combo, [("something"), ("something")])

    def idose(self, irc, msg, args, dose, name, method):
        """<amt> <drug> <method> logs a dose to keep track of
        """
        r = requests.get(URL_DRUG, params={f"name": name}).json()
        found_method = False
        onset = None
        if not r['err']:
            drug = r['data'][0]
            drug_name = r['data'][0]['pretty_name']
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
        drug_and_method = drug_name
        if method:
            if not found_method:
                method = method.title()

            drug_and_method = "%s via %s" % (drug_and_method, method)

        time = datetime.utcnow()
        dose_data[str(msg.nick)] = { 'time': str(time), 'dose': dose, 'drug': drug_name, 'method': method }
        re = f"Dosed {dose} of {drug_and_method} at {str(time)}"

        if not onset == None:
            re += f". You should start feeling effects {onset} from now"
        irc.reply(re)
    idose = wrap(idose, [("something"), ("something"), ("something")])

    def lastdose(self, irc, msg, args):
        """ retrieves saved dose
        """
        if str(msg.nick) in dose_data:
            lastdose = dose_data[str(msg.nick)]
            time = dateutil.parser.isoparse(lastdose['time'])
            re = f"You last dosed {lastdose['dose']} of {lastdose['drug']} via {lastdose['method']} at {time}"
            irc.reply(re)
        else:
            irc.error('No last dose saved for you')

    lastdose = wrap(lastdose)







Class = Tripsit


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
