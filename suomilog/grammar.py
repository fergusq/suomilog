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

from abc import ABC, abstractmethod
from typing import Callable, Self, Sequence


class Token:
	def __init__(self, token: str, alternatives: list[tuple[str, set[str]]]):
		self.token = token
		self.alternatives = alternatives

	def __repr__(self) -> str:
		return "Token(" + repr(self.token) + ", " + repr(self.alternatives) + ")"

	def __str__(self) -> str:
		return self.token + "[" + "/".join([baseform + "{" + ", ".join(bits) + "}" for baseform, bits in self.alternatives]) + "]"

	def to_code(self) -> str:
		return self.token or "/".join([baseform + "{" + ",".join(bits) + "}" for baseform, bits in self.alternatives])

	def contains_match(self, alternatives: list[tuple[str, set[str]]]) -> bool:
		return any([any([tbf == baseform and tbits >= bits for tbf, tbits in self.alternatives]) for baseform, bits in alternatives])

	def to_alternatives(self, bits: set[str]) -> list[tuple[str, set[str]]]:
		return [(wbf, (wbits-{"$"})|(bits if "$" in wbits else wbits)) for wbf, wbits in self.alternatives]

	def baseform(self, *tbits: str):
		tbits_set = set(tbits)
		for baseform, bits in self.alternatives:
			if tbits_set <= bits:
				return baseform
		return None

	def bits(self) -> set[str]:
		bits = set()
		for _, b in self.alternatives:
			bits.update(b)
		return bits


class Nonterminal:
	def __init__(self, name: str, bits: set[str], unexpanded: "Nonterminal | None" = None):
		self.name = name
		self.bits = bits
		self.unexpanded = unexpanded

	def __repr__(self):
		return "Nonterminal(" + repr(self.name) + ", " + repr(self.bits) +  ((", unexpanded=" + repr(self.unexpanded)) if self.unexpanded else "") + ")"

	def to_code(self):
		return "." + self.name + ("{" + ",".join(self.bits) + "}" if self.bits else "")


class Output[OutputT]:
	def eval(self, args: Sequence[OutputT]) -> OutputT:
		raise NotImplementedError()


class StringOutput(Output[str]):
	def __init__(self, string: str):
		self.string = string

	def __repr__(self):
		return "StringOutput(" + repr(self.string) + ")"

	def eval(self, args):
		args = [arg.token if isinstance(arg, Token) else str(arg) for arg in args]
		ans = self.string
		for i, a in enumerate(args):
			var = "$"+str(i+1)
			if var not in ans:
				ans = ans.replace("$*", ",".join(args[i:]))
				break
			ans = ans.replace(var, str(a))
		return ans


class Grammar[OutputT]:
	rules: dict[str, list["BaseRule[OutputT]"]]
	"""
	A mapping from nonterminals to rules.
	"""

	def __init__(self, rules: dict[str, list["BaseRule[OutputT]"]] | None = None, names: dict[str, str] | None = None):
		self.rules = rules or {}

	def print(self):
		for nonterminal_name in sorted(self.rules):
			print(nonterminal_name, "::=")
			for rule in self.rules[nonterminal_name]:
				print(" " + rule.to_code())

	def copy(self):
		return Grammar({name: self.rules[name].copy() for name in self.rules})

	def update(self, grammar: "Grammar"):
		for nonterminal_name in grammar.rules:
			if nonterminal_name in self.rules:
				self.rules[nonterminal_name] += grammar.rules[nonterminal_name]
			else:
				self.rules[nonterminal_name] = grammar.rules[nonterminal_name].copy()

	def parse_grammar_line(self, line: str, output: Output[OutputT] | None = None, default_output: Callable[[str], Output[OutputT]] | None = StringOutput):
		if debug_level >= 1:
			print(line)

		tokens = line.replace("\t", " ").split(" ")
		if len(tokens) > 2 and tokens[0].startswith(".") and tokens[1] == "::=" and (output is not None or "->" in tokens):
			end = tokens.index("->") if "->" in tokens else len(tokens)
			nonterminal = tokens[0][1:]
			bits = set()
			if "{" in nonterminal and nonterminal[-1] == "}":
				bits = set(",".split(nonterminal[nonterminal.index("{")+1:-1]))
				nonterminal = nonterminal[nonterminal.index("{")]
			words = []
			for token in tokens[2:end]:
				word = parse_word_in_grammar_line(token)
				if not word:
					continue
					
				words.append(word)

			if nonterminal not in self.rules:
				self.rules[nonterminal] = []

			if "->" in tokens:
				if output is not None or default_output is None:
					raise ValueError("Grammar line must have exactly one Output object. Ensure that `output` is not set if the grammar line has output code after an arrow `->`. If output code is present, the `default_output` must not be None.")

				output_code = " ".join(tokens[end+1:])
				output = default_output(output_code)

			assert output is not None
			rule = ProductionRule(nonterminal, words, output, bits)
			self.rules[nonterminal].append(rule)
			return rule
		else:
			raise Exception("Syntax error on line `" + line + "'")

	def expand_bits(self, nonterminal: str, bits: set[str], extended: dict[str, list["BaseRule[OutputT]"]] | None = None) -> dict[str, list["BaseRule[OutputT]"]]:
		if nonterminal not in self.rules:
			return {}
		
		ans: dict[str, list[BaseRule[OutputT]]] = extended or {}
		name = "." + nonterminal + "{" + ",".join(sorted(bits)) + "}"
		if name in ans:
			return ans

		ans[name] = []
		for rule in self.rules[nonterminal]:
			ans[name].append(rule.expand_bits(name, self, bits, ans))
		
		return ans


def parse_word_in_grammar_line(token: str) -> Token | Nonterminal | None:
	if "{" in token and token[-1] == "}":
		bits = set(token[token.index("{")+1:-1].split(","))
		token = token[:token.index("{")]
	else:
		bits = set()
	if token == "":
		return None
	elif token == ".":
		return Token(".", [])
	elif token[0] == ".":
		return Nonterminal(token[1:], bits)
	elif bits:
		return Token("", [(token, bits)])
	else:
		return Token(token, [])


debug_level = 0
indent = 0

def set_debug_level(n: int):
	global debug_level
	debug_level = n


class BaseRule[OutputT](ABC):
	@abstractmethod
	def to_code(self) -> str:
		...

	@abstractmethod
	def match(self, grammar: Grammar[OutputT], tokens: list[Token], bits: set[str]) -> list[OutputT]:
		...

	@abstractmethod
	def expand_bits(self, name: str, grammar: Grammar[OutputT], bits: set[str], extended: dict[str, list["BaseRule[OutputT]"]] | None = None) -> Self:
		...


class ProductionRule[OutputT](BaseRule[OutputT]):
	def __init__(self, name: str, words: list[Token | Nonterminal], output: Output[OutputT], bits: set[str] = set()):
		self.name = name
		self.words = words
		self.output = output
		self.bits = set(bits)
		self.positive_bits = set(bit for bit in bits if not bit.startswith("!"))
		self.negative_bits = set(bit[1:] for bit in bits if bit.startswith("!"))

	def __repr__(self):
		return "ProductionRule(" + repr(self.name) + ", " + repr(self.words) + ", " + repr(self.output) + ", bits=" + repr(self.bits) + ")"

	def to_code(self):
		return " ".join([w.to_code() for w in self.words])# + " -> " + repr(self.output)

	def match(self, grammar: Grammar[OutputT], tokens: list[Token], bits: set[str]) -> list[OutputT]:
		raise NotImplementedError("Use the CYKParser to parse this rule")

	def expand_bits(self, name: str, grammar: Grammar[OutputT], bits: set[str], extended: dict[str, list[BaseRule[OutputT]]] | None = None):
		positive_bits = set(bit for bit in bits if not bit.startswith("!"))
		negative_bits = set(bit[1:] for bit in bits if bit.startswith("!"))
		if not self.positive_bits <= positive_bits or self.negative_bits & positive_bits or self.positive_bits & negative_bits:
			return ProductionRule(name, [Token("<FALSE>", [])], self.output)
		
		ans = []
		for word in self.words:
			if isinstance(word, Nonterminal):
				new_bits = (word.bits-{"$"})|(bits if "$" in word.bits else set())
				new_name = "." + word.name + "{" + ",".join(sorted(new_bits)) + "}"
				grammar.expand_bits(word.name, new_bits, extended)
				ans += [Nonterminal(new_name, set(), unexpanded=word)]
			
			elif isinstance(word, Token):
				new_alternatives = [(wbf, (wbits-{"$"})|(bits if "$" in wbits else set())) for wbf, wbits in word.alternatives]
				ans += [Token(word.token, new_alternatives)]
			
			else:
				assert False
		
		return ProductionRule(name, ans, self.output)