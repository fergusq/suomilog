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
		baseforms = set()
		bits = set()
		for word in voikko.analyze(token.tokenText):
			if "BASEFORM" in word:
				bf, bs = baseformAndBits(word)
				baseforms.add(bf)
				bits |= bs
		tokens.append(pp.Token(token.tokenText, baseforms, bits))
	return tokens

def baseformAndBits(word):
	bits = set()
	addBits(word, bits, "NUMBER", {"singular": "yksikkö", "plural": "monikko"})
	addBits(word, bits, "SIJAMUOTO")
	return word["BASEFORM"], bits

def addBits(word, bits, name, table=None):
	if name in word:
		if table:
			if word[name] in table:
				bits.add(table[word[name]])
		else:
			bits.add(word[name])
