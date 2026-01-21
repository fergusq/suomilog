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

import argparse
import os
from typing import Literal, Sequence

import suomilog.cykparser as cyk
import suomilog.patternparser as pp
import suomilog.finnish as fiutils


type AnnotatedToken = tuple[str, Literal["normal", "noinfl", "nonlemma_infl"]]
type OutputT = tuple[AnnotatedToken, ...]


class ReinflectorOutput(pp.Output[OutputT]):
	def __init__(self, output: str):
		# Jäsentää ulostulokoodin ("->" jälkeen tulevan koodin kieliopissa)
		words: list[AnnotatedToken] = [("", "normal")]
		noinfl_depth = 0
		nonlemma_infl_depth = 0
		for char in output:
			if char == "(":
				noinfl_depth += 1
			
			elif char == ")":
				noinfl_depth -= 1
			
			elif char == "[":
				nonlemma_infl_depth += 1
			
			elif char == "]":
				nonlemma_infl_depth -= 1
			
			else:
				if noinfl_depth > 0:
					state = "noinfl"
				
				elif nonlemma_infl_depth > 0:
					state = "nonlemma_infl"
				
				else:
					state = "normal"
			
				if char == " ":
					words.append(("", state))
				
				else:
					words = words[:-1] + [(words[-1][0] + char, state)]
		
		self.annotations = words

	def eval(self, args: Sequence[OutputT]) -> OutputT:
		argsmap = {f"${i+1}": arg for i, arg in enumerate(args)}
		ans: list[AnnotatedToken] = []
		for variable, state in self.annotations:
			if variable not in argsmap:
				raise Exception("Rule does not produce variable " + variable)

			# Muuttujaa taivutetaan normaalisti, eli samalla tavalla kuin sisemmät säännöt taivuttavat sitä
			if state == "normal":
				ans += argsmap[variable]
			
			# Muussa tapauksessa ylikirjoitetaan sisemmän säännön taivutussääntö tämän säännön taivutussäännöllä
			else:
				for token, _ in argsmap[variable]:
					ans.append((token, state))
		
		return tuple(ans)


def match_bits(tbits: set[str], bits: set[str]):
	positive_bits = {bit for bit in bits if not bit.startswith("!")}
	negative_bits = {bit[1:] for bit in bits if bit.startswith("!")}
	return tbits >= positive_bits and not (tbits & negative_bits)


class WordPattern(pp.BasePattern[OutputT]):
	def __init__(self, bits: set[str] = set()):
		self.bits = set() | bits

	def __repr__(self):
		return f"WordPattern({repr(self.bits)})"

	def toCode(self):
		if not self.bits:
			return "<pattern that matches any single token>"
		
		else:
			return f"<pattern that matches any single token with bits {{{','.join(self.bits)}}}>"

	def match(self, grammar: pp.Grammar[OutputT], tokens: list[pp.Token], bits: set[str]) -> list[OutputT]:
		bits = self.bits|bits
		if len(tokens) != 1 or bits and not any(match_bits(altbits, bits) for _, altbits in tokens[0].alternatives):
			return []

		return [((tokens[0].token, "normal"),)]

	def allowsEmptyContent(self):
		return False

	def expandBits(self, name: str, grammar: pp.Grammar[OutputT], bits: set[str], extended=None):
		return WordPattern(self.bits | bits)


def main():
	argparser = argparse.ArgumentParser()
	argparser.add_argument("-d", "--debug", action="store_true")
	argparser.add_argument("plural_tag", choices=["+sg", "+pl"])
	argparser.add_argument("case_tag", choices=fiutils.SINGULAR_AND_PLURAL_CASES+fiutils.PLURAL_CASES)
	args = argparser.parse_args()

	if args.debug:
		import readline

	grammar: pp.Grammar[OutputT] = pp.Grammar()

	grammar.patterns["."] = [
		WordPattern()
	]

	path = os.path.dirname(os.path.realpath(__file__))
	with open(os.path.join(path, "np.suomilog")) as file:
		for line in file:
			if "::=" in line and not line.startswith("#"):
				grammar.parseGrammarLine(line.replace("\n", ""), default_output=ReinflectorOutput)

	parser = cyk.CYKParser(grammar, "ROOT")
	
	if args.debug:
		n_patterns = sum([len(category) for category in grammar.patterns.values()])
		print("Ladattu", n_patterns, "fraasia.")
		grammar.print()
		#parser.print()

	while True:
		try:
			line = input(">> " if args.debug else "")

		except EOFError:
			print()
			break

		if not line:
			continue

		else:
			tokens = fiutils.tokenize(line)
			if args.debug:
				print(tokens)

			analysis = parser.parse(tokens)
			outputs = analysis.getOutput(".ROOT{}")
			if not outputs:
				if args.debug:
					print("Jäsennys epäonnistui.")
					print(analysis.cyk_table)
					print(analysis.split_table)
				
				else:
					print()  # Tulostetaan tyhjä rivi jos epäonnistuttiin

				continue
			
			for output in outputs:
				inflected = []
				for token, state in output:
					if state == "normal" or state == "nonlemma_infl":
						token = list(fiutils.inflect_nominal(token, args.case_tag, args.plural_tag))[0]
					
					inflected.append(token)

				if args.debug:
					print(args.plural_tag + args.case_tag + " ->", " ".join(inflected))

				else:
					print(" ".join(inflected))
					break  # Halutaan vain yksi tulos ei-debugtilassa


if __name__ == "__main__":
	main()