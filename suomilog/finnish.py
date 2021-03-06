# Suomilog
# Copyright (C) 2019 Iikka Hauhio
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import re
from collections import defaultdict
from voikko import libvoikko as lv
from voikko.inflect_word import inflect_word
from . import patternparser as pp

DICTIONARY = defaultdict(list)

voikko = lv.Voikko("fi-x-morpho")

def tokenize(text):
	tokens = []
	for token in voikko.tokens(text):
		if token.tokenType == lv.Token.WHITESPACE:
			continue
		if "-" in token.tokenText:
			index = token.tokenText.rindex("-")+1
			lastPart = token.tokenText[index:]
			baseformPrefix = token.tokenText[:index].lower()
		else:
			lastPart = token.tokenText
			baseformPrefix = ""
		alternatives = []
		for word in voikko.analyze(token.tokenText):
			if "BASEFORM" in word:
				alternatives.append(baseformAndBits(word))
		# Jos jäsennys epäonnistui, koetetaan jäsennystä vain viimeisen palan kautta
		if len(alternatives) == 0 and baseformPrefix:
			for word in voikko.analyze(lastPart):
				if "BASEFORM" in word:
					alternatives.append(baseformAndBits(word, baseformPrefix))
		# Jos sana löytyy suomilogin omasta sanakirjasta, lisää myös sieltä vaihtoehdot
		if token.tokenText.lower() in DICTIONARY:
			alternatives += DICTIONARY[token.tokenText.lower()]
		tokens.append(pp.Token(token.tokenText, alternatives))
	return tokens

def baseformAndBits(word, baseformPrefix=None):
	bits = set()
	addBits(word, bits, "NUMBER", {"singular": "yksikkö", "plural": "monikko"})
	addBits(word, bits, "SIJAMUOTO")
	addBits(word, bits, "CLASS")
	addBits(word, bits, "PARTICIPLE")
	addBits(word, bits, "PERSON")
	addBits(word, bits, "MOOD", {
		"MINEN-infinitive": "-minen",
		"MA-infinitive": "-ma",
		"E-infinitive": "-e",
		"A-infinitive": "-a",
		"imperative": "imperatiivi",
		"indicative": "indikatiivi",
		"conditional": "konditionaali",
		"potential": "potentiaali"
	})
	if word["CLASS"] == "lukusana" and ("SIJAMUOTO" not in word or not word["SIJAMUOTO"]):
		bits.add("nimento")
	if not baseformPrefix:
		return word["BASEFORM"].lower(), bits
	else:
		return baseformPrefix + word["BASEFORM"].lower(), bits

def addBits(word, bits, name, table=None):
	if name in word:
		if table:
			if word[name] in table:
				bits.add(table[word[name]])
		else:
			bits.add(word[name])

def addNounToDictionary(noun):
	for plural in [False, True]:
		for case in CASES:
			DICTIONARY[inflect(noun, case, plural).lower()].append((noun, {case, "monikko" if plural else "yksikkö"}))

CASES = [
	"nimento",
	"omanto",
	"osanto",
	"olento",
	"tulento",
	"ulkoolento",
	"ulkotulento",
	"ulkoeronto",
	"sisaolento",
	"sisatulento",
	"sisaeronto",
	"vajanto"
]

CASES_LATIN = {
	"nimento": "nominatiivi",
	"omanto": "genetiivi",
	"osanto": "partitiivi",
	"olento": "essiivi",
	"tulento": "translatiivi",
	"ulkotulento": "allatiivi",
	"ulkoolento": "adessiivi",
	"ulkoeronto": "ablatiivi",
	"sisatulento": "illatiivi",
	"sisaolento": "inessiivi",
	"sisaeronto": "elatiivi",
	"vajanto": "abessiivi",
	"keinonto": "instruktiivi",
	"seuranto": "komitatiivi",
	"kerrontosti": "adverbi"
}

CASES_ENGLISH = {
	"nimento": "nominative",
	"omanto": "genitive",
	"osanto": "partitive",
	"olento": "essive",
	"tulento": "translative",
	"ulkotulento": "allative",
	"ulkoolento": "adessive",
	"ulkoeronto": "ablative",
	"sisatulento": "illative",
	"sisaolento": "inessive",
	"sisaeronto": "elative",
	"vajanto": "abessive",
	"keinonto": "instructive",
	"seuranto": "comitative",
	"kerrontosti": "adverb"
}

CASES_A = {
	"nimento": "",
	"omanto": ":n",
	"osanto": ":ta",
	"olento": ":na",
	"tulento": ":ksi",
	"ulkotulento": ":lle",
	"ulkoolento": ":lla",
	"ulkoeronto": ":lta",
	"sisatulento": ":han",
	"sisaolento": ":ssa",
	"sisaeronto": ":sta",
	"vajanto": ":tta",
	"keinonto": ":in",
	"seuranto": ":ineen",
	"kerrontosti": ":sti"
}

CASES_F = {
	"nimento": "",
	"omanto": ":n",
	"osanto": ":ää",
	"olento": ":nä",
	"tulento": ":ksi",
	"ulkotulento": ":lle",
	"ulkoolento": ":llä",
	"ulkoeronto": ":ltä",
	"sisatulento": ":ään",
	"sisaolento": ":ssä",
	"sisaeronto": ":stä",
	"vajanto": ":ttä",
	"keinonto": ":in",
	"seuranto": ":ineen",
	"kerrontosti": ":sti"
}

CASES_ELLIPSI = {
	"nimento": "",
	"omanto": ":n",
	"osanto": ":ä",
	"olento": ":nä",
	"tulento": ":ksi",
	"ulkotulento": ":lle",
	"ulkoolento": ":llä",
	"ulkoeronto": ":ltä",
	"sisatulento": ":iin",
	"sisaolento": ":ssä",
	"sisaeronto": ":stä",
	"vajanto": ":ttä",
	"keinonto": ":ein",
	"seuranto": ":eineen",
	"kerrontosti": ":sti"
}

CASE_REGEXES = {
	"singular": {
		"omanto": r"[^:]+:n",
		"osanto": r"[^:]+:(aa?|ää?|t[aä])",
		"olento": r"[^:]+:(n[aä])",
		"tulento": r"[^:]+:ksi",
		"ulkotulento": r"[^:]+:lle",
		"ulkoolento": r"[^:]+:ll[aä]",
		"ulkoeronto": r"[^:]+:lt[aä]",
		"sisatulento": r"[^:]+:(aan|ään|h[aeiouyäöå]n)",
		"sisaolento": r"[^:]+:ss[aä]",
		"sisaeronto": r"[^:]+:st[aä]",
		"vajanto": r"[^:]+:tt[aä]"
	},
	"plural": {
		"omanto": r"[^:]+:ien",
		"osanto": r"[^:]+:(ia?|iä?|it[aä])",
		"olento": r"[^:]+:(in[aä])",
		"tulento": r"[^:]+:iksi",
		"ulkotulento": r"[^:]+:ille",
		"ulkoolento": r"[^:]+:ill[aä]",
		"ulkoeronto": r"[^:]+:ilt[aä]",
		"sisatulento": r"[^:]+:(iin|ih[aeiouyäöå]n)",
		"sisaolento": r"[^:]+:iss[aä]",
		"sisaeronto": r"[^:]+:ist[aä]",
		"vajanto": r"[^:]+:itt[aä]",
		"keinonto": r"[^:]+:in",
		"seuranto": r"[^:]+:ine[^:]*"
	},
	"": {
		"kerrontosti": "[^:]+:sti"
	}
}

ORDINAL_CASE_REGEXES = {
	"nimento": r"[^:]+:s",
	"omanto": r"[^:]+:nnen",
	"osanto": r"[^:]+:tt[aä]",
	"tulento": r"[^:]+:nneksi",
	"ulkotulento": r"[^:]+:nnelle",
	"ulkoolento": r"[^:]+:nnell[aä]",
	"ulkoeronto": r"[^:]+:nnelt[aä]",
	"sisatulento": r"[^:]+:nteen",
	"sisaolento": r"[^:]+:nness[aä]",
	"sisaeronto": r"[^:]+:nnest[aä]",
	"vajanto": r"[^:]+:nnett[aä]",
	"kerrontosti": r"[^:]+:nnesti"
}

def inflect(word, case, plural):
	case_latin = CASES_LATIN[case]
	if plural:
		case_latin += "_mon"
	
	if re.fullmatch(r"[0-9]+", word):
		if case == "sisatulento":
			if word[-1] in "123560":
				return word + ":een"
			elif word[-1] in "479":
				return word + ":ään"
			else: # 8
				return word + ":aan"
		elif word[-1] in "14579":
			return word + CASES_A[case].replace("a", "ä")
		else:
			return word + CASES_A[case]
	elif len(word) == 1:
		if word in "flmnrsx":
			return word + CASES_F[case]
		elif case == "sisatulento":
			if word in "aeiouyäöå":
				return word + ":h" + word + "n"
			elif word in "bcdgptvw":
				return word + ":hen"
			elif word in "hk":
				return word + ":hon"
			elif word == "j":
				return "j:hin"
			elif word == "q":
				return "q:hun"
			elif word == "z":
				return "z:aan"
		elif word in "ahkoquzå":
			return word + CASES_A[case]
		else:
			return word + CASES_A[case].replace("a", "ä")
	else:
		inflections = inflect_word(word)
		if case_latin not in inflections:
			return word + ":" + case
		return inflections[case_latin]
