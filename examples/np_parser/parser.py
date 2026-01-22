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
from typing import Literal, NamedTuple, Sequence

import suomilog
import suomilog.finnish as fiutils


type AnnotatedToken = tuple[str, Literal["normal", "noinfl", "nonlemma_infl"]]


class OutputT(NamedTuple):
	tokens: tuple[AnnotatedToken, ...]
	weight: float


class ReinflectorOutput(suomilog.Output[OutputT]):
	def __init__(self, output: str):
		# Jäsentää ulostulokoodin ("->" jälkeen tulevan koodin kieliopissa)
		if "::" in output:
			fields = output.split("::")
			assert len(fields) == 2
			output = fields[0].strip()
			self.weight = float(fields[1])
		
		else:
			self.weight = 0.0

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
		tokens: list[AnnotatedToken] = []
		weight = self.weight
		for variable, state in self.annotations:
			if variable not in argsmap:
				raise Exception("Rule does not produce variable " + variable)

			# Muuttujaa taivutetaan normaalisti, eli samalla tavalla kuin sisemmät säännöt taivuttavat sitä
			if state == "normal":
				tokens += argsmap[variable].tokens
				weight += argsmap[variable].weight
			
			# Muussa tapauksessa ylikirjoitetaan sisemmän säännön taivutussääntö tämän säännön taivutussäännöllä
			else:
				for token, _ in argsmap[variable].tokens:
					tokens.append((token, state))
				
				weight += argsmap[variable].weight
		
		return OutputT(tuple(tokens), weight)


def match_bits(tbits: set[str], bits: set[str]):
	positive_bits = {bit for bit in bits if not bit.startswith("!")}
	negative_bits = {bit[1:] for bit in bits if bit.startswith("!")}
	return tbits >= positive_bits and not (tbits & negative_bits)


class WordRule(suomilog.BaseRule[OutputT]):
	def __init__(self, bits: set[str] = set()):
		self.bits = set() | bits

	def __repr__(self):
		return f"WordRule({repr(self.bits)})"

	def to_code(self):
		if not self.bits:
			return "<rule that matches any single token>"
		
		else:
			return f"<rule that matches any single token with bits {{{','.join(self.bits)}}}>"

	def match(self, grammar: suomilog.Grammar[OutputT], tokens: list[suomilog.Token], bits: set[str]) -> list[OutputT]:
		bits = self.bits|bits
		if len(tokens) != 1 or bits and not any(match_bits(altbits, bits) for _, altbits in tokens[0].alternatives):
			return []

		return [OutputT(((tokens[0].token, "normal"),), 0.0)]

	def expand_bits(self, name: str, grammar: suomilog.Grammar[OutputT], bits: set[str], extended=None):
		return WordRule(self.bits | bits)


def main():
	argparser = argparse.ArgumentParser()
	argparser.add_argument("-d", "--debug", action="store_true")
	argparser.add_argument("plural_tag", choices=["+sg", "+pl"])
	argparser.add_argument("case_tag", choices=fiutils.SINGULAR_AND_PLURAL_CASES+fiutils.PLURAL_CASES)
	args = argparser.parse_args()

	if args.debug:
		import readline

	grammar: suomilog.Grammar[OutputT] = suomilog.Grammar()

	grammar.rules["."] = [
		WordRule()
	]

	path = os.path.dirname(os.path.realpath(__file__))
	with open(os.path.join(path, "np.suomilog")) as file:
		for line in file:
			if "::=" in line and not line.startswith("#"):
				grammar.parse_grammar_line(line.replace("\n", ""), default_output=ReinflectorOutput)

	parser = suomilog.CYKParser(grammar, "ROOT")
	
	if args.debug:
		n_rules = sum([len(category) for category in grammar.rules.values()])
		print("Ladattu", n_rules, "fraasia.")
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
			outputs = analysis.get_output(".ROOT{}")
			if not outputs:
				if args.debug:
					print("Jäsennys epäonnistui.")
					analysis.print()
					print(analysis.split_table)
				
				else:
					print()  # Tulostetaan tyhjä rivi jos epäonnistuttiin

				continue
			
			for output in sorted(outputs, key=lambda o: o.weight):
				inflected = []
				for token, state in output.tokens:
					if state == "normal" or state == "nonlemma_infl":
						token = list(fiutils.inflect_nominal(token, args.case_tag, args.plural_tag))[0]
					
					inflected.append(token)

				if args.debug:
					print(args.plural_tag + args.case_tag + " ->", " ".join(inflected), f"(paino: {output.weight})")

				else:
					print(" ".join(inflected))
					break  # Halutaan vain yksi tulos ei-debugtilassa


if __name__ == "__main__":
	main()