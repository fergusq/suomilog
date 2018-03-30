# Suomilog
# Copyright (C) 2018 Iikka Hauhio
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

from voikko import libvoikko as lv
from . import patternparser as pp

voikko = lv.Voikko("fi-x-morpho")

def tokenize(text):
	tokens = []
	for token in voikko.tokens(text):
		if token.tokenType == lv.Token.WHITESPACE:
			continue
		alternatives = []
		for word in voikko.analyze(token.tokenText):
			if "BASEFORM" in word:
				alternatives.append(baseformAndBits(word))
		tokens.append(pp.Token(token.tokenText.lower(), alternatives))
	return tokens

def baseformAndBits(word):
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
	return word["BASEFORM"], bits

def addBits(word, bits, name, table=None):
	if name in word:
		if table:
			if word[name] in table:
				bits.add(table[word[name]])
		else:
			bits.add(word[name])

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
