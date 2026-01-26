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
from typing import AbstractSet, Literal, NamedTuple, Sequence
import itertools
import functools

import suomilog
import suomilog.finnish as fiutils


type Annotation = Literal["normal", "noinfl", "nonlemma_infl"]


class AnnotatedToken(NamedTuple):
	token: str
	bits: AbstractSet[str]
	annotation: Annotation


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

		words: list[tuple[str, Annotation]] = [("", "normal")]
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
		argsmap: dict[str, OutputT] = {f"${i+1}": arg for i, arg in enumerate(args)}
		tokens: list[AnnotatedToken] = []
		weight = self.weight
		for variable, state in self.annotations:
			if "{" in variable and variable.endswith("}"):
				i = variable.index("{")
				bits = frozenset(variable[i+1:-1].split(","))
				variable = variable[:i]

			else:
				bits = frozenset({"$"})

			if not variable.startswith("$"):
				# tämä ei olekaan muuttuja vaan tokeni
				tokens.append(AnnotatedToken(variable, bits, state))
				continue

			assert variable in argsmap, f"Variable {variable} does not exist (variables={argsmap})"

			# Muuttujaa taivutetaan normaalisti, eli samalla tavalla kuin sisemmät säännöt taivuttavat sitä
			if state == "normal":
				for token in argsmap[variable].tokens:
					tokens.append(AnnotatedToken(token.token, suomilog.merge_bits(bits, token.bits), token.annotation))

				weight += argsmap[variable].weight
			
			# Muussa tapauksessa ylikirjoitetaan sisemmän säännön taivutussääntö tämän säännön taivutussäännöllä (paitsi jos sana ei taivu)
			else:
				for token in argsmap[variable].tokens:
					new_annotation = "noinfl" if token.annotation == "noinfl" else state
					tokens.append(AnnotatedToken(token.token, suomilog.merge_bits(bits, token.bits), new_annotation))
				
				weight += argsmap[variable].weight
		
		return OutputT(tuple(tokens), weight)


class WordRule(suomilog.BaseRule[OutputT]):
	def __init__(self, bits: AbstractSet[str] = frozenset()):
		self.bits = frozenset() | bits

	def __repr__(self):
		return f"WordRule({repr(self.bits)})"

	def to_code(self):
		if not self.bits:
			return "<rule that matches any single token>"
		
		else:
			return f"<rule that matches any single token with bits {{{','.join(self.bits)}}}>"

	def match(self, grammar: suomilog.Grammar[OutputT], tokens: Sequence[suomilog.Token], bits: AbstractSet[str]) -> list[OutputT]:
		bits = self.bits|bits
		if len(tokens) != 1 or bits and not any(suomilog.match_bits(altbits, bits) for _, altbits in tokens[0].alternatives):
			return []

		tokenizer_bits = {bit for _, altbits in tokens[0].alternatives for bit in altbits if bit.startswith("-")}

		return [OutputT((AnnotatedToken(tokens[0].surfaceform, frozenset(tokenizer_bits), "normal"),), 0.0)]

	def expand_bits(self, name: str, grammar: suomilog.Grammar[OutputT], bits: AbstractSet[str], extended=None):
		return WordRule(self.bits | bits)

@functools.cache
def get_parser():
	grammar: suomilog.Grammar[OutputT] = suomilog.Grammar()

	grammar.rules["."] = [
		WordRule()
	]

	path = os.path.dirname(os.path.realpath(__file__))
	with open(os.path.join(path, "np.suomilog")) as file:
		for line in file:
			if "::=" in line and not line.startswith("#"):
				grammar.parse_grammar_line(line.replace("\n", ""), default_output=ReinflectorOutput)

			elif line.startswith("$"):
				grammar.parse_variable_line(line.strip())

	return suomilog.CYKParser(grammar, "ROOT")

def reinflect(term: str, plural_tag: str, case_tag: str, poss: str = "") -> list[str]:
	parser = get_parser()

	tokens = fiutils.tokenize(term)

	analysis = parser.parse(tokens)

	outputs = analysis.get_output(".ROOT{}")
	if not outputs:
		return []

	result = []

	for output in sorted(outputs, key=lambda o: o.weight):
		inflected: list[list[str]] = []
		for token in output.tokens:
			inflected.append(reinflect_token(token, plural_tag, case_tag, poss))

		result.extend([" ".join(x) for x in itertools.product(*inflected)])

	return result

def reinflect_token(token: AnnotatedToken, plural_tag: str, case_tag: str, poss: str) -> list[str]:
	prefix = ""
	suffix = ""
	for bit in token.bits:
		if bit == "-lhyphen":
			prefix = "-" + prefix

		elif bit == "-rhyphen":
			suffix = suffix + "-"

		elif bit == "-lquote":
			prefix = "\"" + prefix

		elif bit == "-rquote":
			suffix = suffix + "\""

	if token.annotation == "normal" or token.annotation == "nonlemma_infl":
		for bit in token.bits:
			if bit in fiutils.SINGULAR_AND_PLURAL_CASES+fiutils.PLURAL_CASES:
				case_tag = bit

			if bit in ["+sg", "+pl"] and case_tag not in ["+com", "+ins"]:
				plural_tag = bit

		return [prefix + t + suffix for t in fiutils.inflect_nominal(token.token, plural_tag, case_tag, poss)]

	else:
		return [prefix + token.token + suffix]

def main():
	argparser = argparse.ArgumentParser()
	argparser.add_argument("-d", "--debug", action="store_true")
	argparser.add_argument("plural_tag", choices=["+sg", "+pl"])
	argparser.add_argument("case_tag", choices=fiutils.SINGULAR_AND_PLURAL_CASES+fiutils.PLURAL_CASES)
	args = argparser.parse_args()

	if args.debug:
		import readline

	parser = get_parser()
	if args.debug:
		parser.grammar.print()

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
			analysis.print()
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
				inflected: list[list[str]] = []
				for token in output.tokens:
					inflected.append(reinflect_token(token, args.plural_tag, args.case_tag, ""))

				results = [" ".join(x) for x in itertools.product(*inflected)]
				if args.debug:
					for result in results:
						print(args.plural_tag + args.case_tag + " ->", result, f"(paino: {output.weight})")

				else:
					print(results[0])
					break  # Halutaan vain yksi tulos ei-debugtilassa


if __name__ == "__main__":
	main()