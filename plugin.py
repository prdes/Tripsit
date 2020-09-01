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
import json
import requests
try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('Tripsit')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x: x

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

Class = Tripsit


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
