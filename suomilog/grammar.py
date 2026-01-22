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
from dataclasses import dataclass
from typing import AbstractSet, Callable, Self, Sequence


def match_bits(tbits: AbstractSet[str], bits: AbstractSet[str]):
	positive_bits = {bit for bit in bits if not bit.startswith("!")}
	negative_bits = {bit[1:] for bit in bits if bit.startswith("!")}
	return tbits >= positive_bits and not (tbits & negative_bits)


def merge_bits(tbits: AbstractSet[str], bits: AbstractSet[str]) -> frozenset[str]:
	"""
	The first argument is the bits on the symbol (including $ and minus bits).
	The second argument is the incoming bits.

	Adds the incoming bits to tbits if tbits contains $.
	Removes any minus bits (bits preceded with a single backslash \\\\).

	For example:
	`merge_bits({"$", "\\\\+pl", "+sg"}, {"+pl", "+nom"}) == {"+sg", "+nom"}`
	"""
	new_bits = (tbits-{"$"}) | (bits if "$" in tbits else set())
	minus_bits = {bit for bit in tbits if bit.startswith("\\")}  # Removes the minus bits themselves
	minus_bits |= {minus_bit[1:] for minus_bit in minus_bits}  # Removes the matching plus bits
	return frozenset(new_bits - minus_bits)


class Token:
	"""
	Represents a token in the text to be parsed, typically a word or punctuation.

	A token is made of two components:
	1. The surfaceform, that is, the form in which the token is present in the tex
	2. A list of analysis alternatives consisting of a baseform and a set of bits.
	"""
	def __init__(self, surfaceform: str, alternatives: list[tuple[str, set[str]]]):
		self.surfaceform = surfaceform
		self.alternatives = alternatives

	def __repr__(self) -> str:
		return "Token(" + repr(self.surfaceform) + ", " + repr(self.alternatives) + ")"

	def __str__(self) -> str:
		return self.surfaceform + "[" + "/".join([baseform + "{" + ", ".join(bits) + "}" for baseform, bits in self.alternatives]) + "]"


class Terminal(ABC):
	"""
	The abstract base class of all terminal symbols.
	"""

	@abstractmethod	
	def to_code(self) -> str:
		...

	@abstractmethod
	def matches_token(self, token: Token) -> bool:
		...

	@abstractmethod
	def expand_bits(self, bits: AbstractSet[str]) -> Self:
		...


@dataclass(frozen=True)
class BaseformTerminal(Terminal):
	"""
	A terminal that matches to tokens that have at least one alternative with the given baseform and bits.
	"""
	baseform: str
	bits: AbstractSet[str]

	def to_code(self) -> str:
		return self.baseform + "{" + ",".join(self.bits) + "}"

	def matches_token(self, token: Token) -> bool:
		return any([tbf == self.baseform and match_bits(tbits, self.bits) for tbf, tbits in token.alternatives])

	def expand_bits(self, bits: AbstractSet[str]) -> "BaseformTerminal":
		new_bits = merge_bits(self.bits, bits)
		return BaseformTerminal(self.baseform, new_bits)


@dataclass(frozen=True)
class SurfaceformTerminal(Terminal):
	"""
	A terminal that matches to tokens with the correct surfaceform.
	"""
	surfaceform: str

	def to_code(self) -> str:
		return self.surfaceform

	def matches_token(self, token: Token) -> bool:
		return token.surfaceform == self.surfaceform

	def expand_bits(self, bits: AbstractSet[str]) -> "SurfaceformTerminal":
		return self


@dataclass(frozen=True)
class Nonterminal:
	"""
	A nonterminal that can appear on the right side of a production rule.
	"""
	name: str
	bits: AbstractSet[str]
	unexpanded: "Nonterminal | None" = None

	def to_code(self):
		return "." + self.name + ("{" + ",".join(self.bits) + "}" if self.bits else "")


type TerminalOrNonterminal = Terminal | Nonterminal


class Output[OutputT](ABC):
	"""
	A base class for rule outputs.
	"""

	@abstractmethod
	def eval(self, args: Sequence[OutputT]) -> OutputT:
		"""
		Constructs the output of the rule. `args` contains the outputs of the nonterminals in the rule.
		"""
		...


class StringOutput(Output[str]):
	"""
	A simple output method that treats the output code as a template string and subtitutes variables $1, $2, and so on with the outputs of the first nonterminal, the second nonterminal, and so on.
	"""
	def __init__(self, string: str):
		self.string = string

	def __repr__(self):
		return "StringOutput(" + repr(self.string) + ")"

	def eval(self, args):
		args = [arg.surfaceform if isinstance(arg, Token) else str(arg) for arg in args]
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
	A mapping from nonterminal names to rules.
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
			nonterminal_name = tokens[0][1:]
			bits = set()
			if "{" in nonterminal_name and nonterminal_name[-1] == "}":
				bits = set(",".split(nonterminal_name[nonterminal_name.index("{")+1:-1]))
				nonterminal_name = nonterminal_name[nonterminal_name.index("{")]

			words: list[TerminalOrNonterminal] = []
			for token in tokens[2:end]:
				word = parse_word_in_grammar_line(token)
				if not word:
					continue
					
				words.append(word)

			if nonterminal_name not in self.rules:
				self.rules[nonterminal_name] = []

			if "->" in tokens:
				if output is not None or default_output is None:
					raise ValueError("Grammar line must have exactly one Output object. Ensure that `output` is not set if the grammar line has output code after an arrow `->`. If output code is present, the `default_output` must not be None.")

				output_code = " ".join(tokens[end+1:])
				output = default_output(output_code)

			assert output is not None
			rule = ProductionRule(nonterminal_name, words, output, bits)
			self.rules[nonterminal_name].append(rule)
			return rule
		else:
			raise Exception("Syntax error on line `" + line + "'")

	def expand_bits(self, nonterminal_name: str, bits: AbstractSet[str], extended: dict[str, list["BaseRule[OutputT]"]] | None = None) -> tuple[str, dict[str, list["BaseRule[OutputT]"]]]:
		if nonterminal_name not in self.rules:
			return nonterminal_name, {}
		
		ans: dict[str, list[BaseRule[OutputT]]] = extended or {}
		name = "." + nonterminal_name + "{" + ",".join(sorted(bits)) + "}"
		if name in ans:
			return name, ans

		ans[name] = []
		for rule in self.rules[nonterminal_name]:
			ans[name].append(rule.expand_bits(name, self, bits, ans))
		
		return name, ans


def parse_word_in_grammar_line(token: str) -> BaseformTerminal | SurfaceformTerminal | Nonterminal | None:
	if "{" in token and token[-1] == "}":
		has_bits = True
		bits = set(token[token.index("{")+1:-1].split(","))
		token = token[:token.index("{")]
	else:
		has_bits = False
		bits = set()

	if token == "":
		return None
	elif token.startswith(".") and token != ".":
		return Nonterminal(token[1:], bits)
	elif has_bits:
		return BaseformTerminal(token, bits)
	else:
		return SurfaceformTerminal(token)


debug_level = 0
indent = 0

def set_debug_level(n: int):
	global debug_level
	debug_level = n


class BaseRule[OutputT](ABC):
	"""
	Base class of all rules.

	Custom parsing algorithms can be implemented by overriding the `match` method that will be called for each range of tokens.
	"""
	@abstractmethod
	def to_code(self) -> str:
		...

	@abstractmethod
	def match(self, grammar: Grammar[OutputT], tokens: Sequence[Token], bits: AbstractSet[str]) -> list[OutputT]:
		"""
		The CYK parser calls this method for each range of tokens.
		If it returns a non-empty list, then this rule is considered to match the range.
		"""
		...

	@abstractmethod
	def expand_bits(self, name: str, grammar: Grammar[OutputT], bits: AbstractSet[str], extended: dict[str, list["BaseRule[OutputT]"]] | None = None) -> Self:
		...


class ProductionRule[OutputT](BaseRule[OutputT]):
	"""
	Represents a production rule. On the left side of the rule is a nonterminal name, on the right side is a list of terminals and nonterminals.
	"""

	nonterminal_name: str
	"""
	The left side of the rule: the name of the nonterminal that produces the right side.
	"""

	words: Sequence[TerminalOrNonterminal]
	"""
	The right side of the rule: a sequence of nonterminals and terminals this rule matches to.
	"""

	output: Output[OutputT]
	"""
	The Output object used to produce the output of this rule.
	"""

	bits: set[str]
	"""
	When expanded, this rule can only be expanded if $ matches these bits.
	"""

	def __init__(self, nonterminal_name: str, words: Sequence[TerminalOrNonterminal], output: Output[OutputT], bits: set[str] = set()):
		self.nonterminal_name = nonterminal_name
		self.words = words
		self.output = output
		self.bits = set(bits)
		self.positive_bits = set(bit for bit in bits if not bit.startswith("!"))
		self.negative_bits = set(bit[1:] for bit in bits if bit.startswith("!"))

	def __repr__(self):
		return "ProductionRule(" + repr(self.nonterminal_name) + ", " + repr(self.words) + ", " + repr(self.output) + ", bits=" + repr(self.bits) + ")"

	def to_code(self):
		return " ".join([w.to_code() for w in self.words])# + " -> " + repr(self.output)

	def match(self, grammar: Grammar[OutputT], tokens: Sequence[Token], bits: AbstractSet[str]) -> list[OutputT]:
		raise NotImplementedError("Use the CYKParser to parse this rule")

	def expand_bits(self, name: str, grammar: Grammar[OutputT], bits: AbstractSet[str], extended: dict[str, list[BaseRule[OutputT]]] | None = None):
		positive_bits = set(bit for bit in bits if not bit.startswith("!"))
		negative_bits = set(bit[1:] for bit in bits if bit.startswith("!"))
		if not self.positive_bits <= positive_bits or self.negative_bits & positive_bits or self.positive_bits & negative_bits:
			return ProductionRule(name, [BaseformTerminal("<FALSE>", {"!"})], self.output)
		
		ans = []
		for word in self.words:
			if isinstance(word, Nonterminal):
				new_bits = merge_bits(word.bits, bits)
				new_name, _ = grammar.expand_bits(word.name, new_bits, extended)
				ans += [Nonterminal(new_name, set(), unexpanded=word)]
			
			else:
				ans.append(word.expand_bits(bits))
		
		return ProductionRule(name, ans, self.output)