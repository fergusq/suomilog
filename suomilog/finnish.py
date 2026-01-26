# Suomilog
# Copyright (C) 2026 Iikka Hauhio
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
import pypykko.utils as pykko
from pypykko.reinflect import reinflect as pykko_reinflect
from pypykko.tokenizer import text2tokens as pykko_tokenize
from . import grammar

DICTIONARY: defaultdict[str, list[grammar.Token]] = defaultdict(list)

def tokenize(text: str) -> list[grammar.Token]:
	old_tokens: list[str] = pykko_tokenize(text)
	new_tokens: list[str] = []
	i = 0
	while i < len(old_tokens):
		if i < len(old_tokens) - 2 and old_tokens[i] == "\"" and old_tokens[i+2] == "\"":
			new_tokens.append("\"" + old_tokens[i+1] + "\"")
			i += 2
			continue

		if i < len(old_tokens) - 1 and old_tokens[i] == "\"":
			new_tokens.append("\"" + old_tokens[i+1])
			i += 1
			continue

		if i < len(old_tokens) - 1 and old_tokens[i+1] == "\"":
			new_tokens.append(old_tokens[i] + "\"")
			i += 1
			continue

		new_tokens.append(old_tokens[i])
		i += 1

	tokens: list[grammar.Token] = []
	token: str
	for token in new_tokens:
		tokenizer_bits = set()
		if token[:1] == "\"":
			token = token[1:]
			tokenizer_bits.add("-lquote")

		if token[-1:] == "\"":
			token = token[:-1]
			tokenizer_bits.add("-rquote")

		if token[:1] == "-":
			token = token[1:]
			tokenizer_bits.add("-lhyphen")

		if token[-1:] == "-":
			token = token[:-1]
			tokenizer_bits.add("-rhyphen")

		if token.strip() == "":
			continue

		alternatives = []
		for word in pykko.analyze(token):
			baseform, bits = baseformAndBits(word)
			bits |= tokenizer_bits
			alternatives.append((baseform, bits))

		# Jos sana löytyy suomilogin omasta sanakirjasta, lisää myös sieltä vaihtoehdot
		if token.lower() in DICTIONARY:
			alternatives += DICTIONARY[token.lower()]

		tokens.append(grammar.Token(token, alternatives))

	return tokens

def baseformAndBits(word: pykko.PykkoAnalysis) -> tuple[str, set[str]]:
	bits: set[str] = set()

	# Lisää kaikki morphtagit bitteinä
	morphtags: list[str] = re.split(r"(?=\+)", word.morphtags)
	bits |= set(morphtags)

	# TODO: Pitäisikö lisätä muitakin yhdistelmiä kuin tämä?
	if "+sg" in bits and "+nom" in bits:
		bits.add("+sg+nom")

	# Lisää sanaluokka, lemma ja pintamuoto bitteinä
	bits.add(f"{word.lemma}:{word.pos}")
	bits.add(f"{word.lemma}:")
	bits.add(f":{word.pos}")
	bits.add(f"«{word.wordform}»")

	return word.lemma, bits

SINGULAR_AND_PLURAL_CASES = [
	"+nom",
	"+gen",
	"+par",
	"+ess",
	"+abe",
	"+tra",
	"+ade",
	"+abl",
	"+all",
	"+ine",
	"+ela",
	"+ill",
]

PLURAL_CASES = [
	"+ins",
	"+com",
]

def inflect_nominal(word: str, plural_tag: str, case_tag: str, poss_tag: str = ""):
	assert plural_tag in ["+sg", "+pl"], plural_tag
	if plural_tag == "+pl":
		assert case_tag in SINGULAR_AND_PLURAL_CASES or case_tag in PLURAL_CASES
	
	else:
		assert case_tag in SINGULAR_AND_PLURAL_CASES

	new_morphtags = []
	for analysis in pykko.analyze(word):
		morphtags: list[str] = re.split(r"(?=\+)", analysis.morphtags)
		new_morphtags = []
		is_nominal = False
		for tag in morphtags:
			if tag == "+conneg":
				is_nominal = False
				break

			if tag == "+sg" or tag == "+pl":
				new_morphtags.append(plural_tag)
				is_nominal = True
			
			elif tag in SINGULAR_AND_PLURAL_CASES or tag in PLURAL_CASES:
				new_morphtags.append(case_tag)
			
			else:
				new_morphtags.append(tag)
		
		if is_nominal:
			break
	
	else:
		new_morphtags = [plural_tag, case_tag]

	new_morphtags.append(poss_tag)

	return pykko_reinflect(word, "".join(new_morphtags))
