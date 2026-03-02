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

from collections import defaultdict
from typing import Hashable, NamedTuple, Sequence
from . import grammar


type CYKTable = defaultdict[tuple[int, int], set[str]]
type SplitTable = defaultdict[tuple[int, int, str], set[int]]
type TokenOutputTable[OutputT] = defaultdict[tuple[int, int, str], set[OutputT]]
type NormalizedOutput[OutputT] = grammar.Output[OutputT] | "DenormalizeStartOutput[OutputT]" | "DenormalizeChainOutput[OutputT]" | "DenormalizeEndOutput[OutputT]"


class CYKParser[OutputT]:
	token_rules: dict[str, grammar.Terminal]
	custom_rules: dict[str, grammar.BaseRule[OutputT]]
	zero_rules: set[str]
	one_rules: defaultdict[str, set[str]]
	one_rules_expanded: defaultdict[str, set[str]]
	two_rules: defaultdict[tuple[str, str], set[str]]
	two_rules_zero_left: defaultdict[str, set[tuple[str, str]]]
	two_rules_zero_right: defaultdict[str, set[tuple[str, str]]]
	outputs: defaultdict[tuple[str, str | tuple[str, str]], list[NormalizedOutput[OutputT]]]
	zero_outputs: dict[str, frozenset[OutputT]]

	def __init__(self, grammar: grammar.Grammar[OutputT], root_nonterminal_name: str):
		self.token_rules = {}
		self.custom_rules = {}
		self.zero_rules = set()
		self.one_rules = defaultdict(set)
		self.one_rules_expanded = defaultdict(set)
		self.two_rules = defaultdict(set)
		self.two_rules_zero_left = defaultdict(set)
		self.two_rules_zero_right = defaultdict(set)
		self.outputs = defaultdict(list)
		self.zero_outputs = {}
		self.grammar = grammar
		self._to_CNF(root_nonterminal_name)

	def _to_CNF(self, root_nonterminal_name: str):
		_, expanded_grammar = self.grammar.expand_bits(root_nonterminal_name, set())
		for nonterminal_name in expanded_grammar:
			for rule in expanded_grammar[nonterminal_name]:
				# ProductionRule-luokka on niille säännöille, jotka voi jäsentää CYK-algoritmilla.
				# On myös sääntöjä, jotka perivät BaseRulen mutta eivät ProductionRulea. Tällöin luokka toteuttaa match-metodin, joka hoitaa jäsentämisen omalla tavallaan.
				if isinstance(rule, grammar.ProductionRule):
					new_words: list[str] = []
					is_nonterminal: list[bool] = []
					for word in rule.words:
						if isinstance(word, grammar.Terminal):
							self.token_rules[word.to_code()] = word
							new_words.append(word.to_code())
							is_nonterminal.append(False)
						
						elif isinstance(word, grammar.Nonterminal):
							new_words.append(word.name)
							is_nonterminal.append(True)
						
						else:
							assert False
					
					if len(new_words) == 1:
						self.one_rules[new_words[0]].add(nonterminal_name)
						self.outputs[(nonterminal_name, new_words[0])].append(rule.output)
					
					else:
						prev = nonterminal_name
						j = id(rule)
						for i in range(len(new_words)-2):
							next = f"{nonterminal_name}_{j}_CONT{i}"
							pair = (new_words[i], next)
							self.two_rules[pair].add(prev)
							self.outputs[(prev, pair)].append(DenormalizeChainOutput(is_nonterminal[i]) if i != 0 else DenormalizeEndOutput(is_nonterminal[i], rule.output))
							prev = next
						
						pair = (new_words[-2], new_words[-1])
						self.two_rules[pair].add(prev)
						self.outputs[(prev, pair)].append(DenormalizeStartOutput(is_nonterminal[-2], is_nonterminal[-1]) if len(new_words) > 2 else rule.output)

				else:
					self.custom_rules[nonterminal_name] = rule
					if rule.allows_empty_content():
						self.zero_rules.add(nonterminal_name)
						self.zero_outputs[nonterminal_name] = frozenset(rule.match(self.grammar, [], set()))

		# Calculating expanded one rules (and expanded two rules containing a zero rule)
		all_symbols = set()
		all_symbols |= self.one_rules.keys()
		for a, b in self.two_rules.keys():
			all_symbols |= {a, b}

		all_symbols |= self.custom_rules.keys()
		for nonterminals in [*self.one_rules.values(), *self.two_rules.values()]:
			all_symbols |= nonterminals

		for a in all_symbols:
			queue = [a]
			while queue:
				rule_name = queue.pop()
				for rule in self.one_rules[rule_name]:
					if rule not in self.one_rules_expanded[a]:
						self.one_rules_expanded[a].add(rule)
						queue.append(rule)

				for zero_rule in self.zero_rules:
					for rule in self.two_rules[(zero_rule, rule_name)]:
						if rule not in self.one_rules_expanded[a]:
							self.one_rules_expanded[a].add(rule)
							self.two_rules_zero_left[rule].add((zero_rule, rule_name))
							queue.append(rule)

					for rule in self.two_rules[(rule_name, zero_rule)]:
						if rule not in self.one_rules_expanded[a]:
							self.one_rules_expanded[a].add(rule)
							self.two_rules_zero_right[rule].add((rule_name, zero_rule))
							queue.append(rule)
	
	def parse(self, tokens: list[grammar.Token]) -> "CYKAnalysis[OutputT]":
		cyk_table: CYKTable = defaultdict(set)
		split_table: SplitTable = defaultdict(set)
		token_outputs: TokenOutputTable = defaultdict(set)
		for i in range(len(tokens)):
			for rule_name, token_rule in self.token_rules.items():
				if token_rule.matches_token(tokens[i]):
					cyk_table[(i, i+1)] |= {rule_name} | self.one_rules_expanded[rule_name]

			for rule_name, custom_rule in self.custom_rules.items():
				if token_output := custom_rule.match(self.grammar, tokens[i:i+1], set()):
					if not all(isinstance(t, Hashable) for t in token_output):
						raise ValueError(f"Output of {rule_name} for {tokens[i:i+1]} is not hashable: {token_output}")
					cyk_table[(i, i+1)] |= {rule_name} | self.one_rules_expanded[rule_name]
					token_outputs[(i, i+1, rule_name)] |= set(token_output)
		
		for span in range(2, len(tokens)+1):
			for start in range(len(tokens)-span+1):
				end = start + span
				for split in range(start+1, end):
					for rule1 in cyk_table[(start, split)]:
						for rule2 in cyk_table[(split, end)]:
							for rule_name in self.two_rules[(rule1, rule2)]:
								cyk_table[(start, end)] |= {rule_name} | self.one_rules_expanded[rule_name]
								split_table[(start, end, rule_name)] |= {split}

				for rule_name, custom_rule in self.custom_rules.items():
					if token_output := custom_rule.match(self.grammar, tokens[start:end], set()):
						if not all(isinstance(t, Hashable) for t in token_output):
							raise ValueError(f"Output of {rule_name} for {tokens[start:end]} is not hashable: {token_output}")
						cyk_table[(start, end)] |= {rule_name} | self.one_rules_expanded[rule_name]
						token_outputs[(start, end, rule_name)] |= set(token_output)
		
		return CYKAnalysis(self, tokens, cyk_table, split_table, token_outputs)

	def print(self):
		print("Token rules:")
		for a, b in self.token_rules.items():
			print(a, "<-", b.to_code())

		print("One rules:")
		for a, B in self.one_rules.items():
			for b in sorted(B):
				print(b, "<-", a)

		print("Two rules:")
		for (a, b), C in self.two_rules.items():
			for c in sorted(C):
				print(c, "<-", a, b)

		print("Zero rules:")
		for b in self.zero_rules:
			print(b, "<-")

		print("Expanded one rules:")
		for a, B in sorted(self.one_rules_expanded.items(), key=lambda i: str(i[1])):
			print(B, "<-", a)

		print("Outputs:")
		for a, b in self.outputs.items():
			print(repr(a), repr(b))

		print("Zero outputs:")
		for a, b in self.zero_outputs.items():
			print(repr(a), repr(b))


class CYKAnalysis[OutputT]:
	memoized_outputs: dict[tuple[str, int, int], frozenset[OutputT | "DenormalizedArgs[OutputT]"] | None]
	def __init__(self, cyk_parser: CYKParser[OutputT], tokens: list[grammar.Token], cyk_table: CYKTable, split_table: SplitTable, token_outputs: TokenOutputTable):
		self.cyk_parser = cyk_parser
		self.tokens = tokens
		self.cyk_table = cyk_table
		self.split_table = split_table
		self.token_outputs = token_outputs
		self.memoized_outputs = {}

	def get_output(self, rule_name: str, start: int = 0, end: int = 0, memoize=True) -> frozenset[OutputT] | None:
		ans = self._get_output(rule_name, start, end, memoize=memoize)
		assert ans is None or all(not isinstance(arg, DenormalizedArgs) for arg in ans)
		return ans  # type: ignore

	def _get_output(self, rule_name: str, start: int, end: int, memoize: bool) -> frozenset[OutputT | "DenormalizedArgs[OutputT]"] | None:
		if end <= 0:
			end = len(self.tokens) - end

		if rule_name not in self.cyk_table[(start, end)]:
			return frozenset()

		if not rule_name.startswith(".") or rule_name == ".":  # jos kyseessä on terminaali
			return None

		if start == end:
			return self.cyk_parser.zero_outputs[rule_name]

		if memoize:
			key = (rule_name, start, end)
			if key in self.memoized_outputs:
				return self.memoized_outputs[key]

		ans: set[OutputT | DenormalizedArgs] = set()
		if token_output := self.token_outputs.get((start, end, rule_name), None):
			ans |= token_output

		for rule in self.cyk_table[(start, end)]:
			for output in self.cyk_parser.outputs.get((rule_name, rule), []):
				args = self.get_output(rule, start, end)
				assert isinstance(output, grammar.Output)
				if args is None:
					ans.add(output.eval(()))
				else:
					for arg in args:
						ans.add(output.eval((arg,)))

		for split in self.split_table[(start, end, rule_name)]:
			for rule1 in self.cyk_table[(start, split)]:
				for rule2 in self.cyk_table[(split, end)]:
					for output in self.cyk_parser.outputs.get((rule_name, (rule1, rule2)), []):
						args1 = self._get_output(rule1, start, split, memoize)
						args2 = self._get_output(rule2, split, end, memoize)

						self._add_two_rule_output(ans, output, args1, args2)

		for zero_rule, rule2 in self.cyk_parser.two_rules_zero_left[rule_name]:
			if rule2 in self.cyk_table[(start, end)]:
				for output in self.cyk_parser.outputs.get((rule_name, (zero_rule, rule2)), []):
					args1 = self.cyk_parser.zero_outputs[zero_rule]
					args2 = self._get_output(rule2, start, end, memoize)
					self._add_two_rule_output(ans, output, args1, args2)

		for rule1, zero_rule in self.cyk_parser.two_rules_zero_right[rule_name]:
			if rule1 in self.cyk_table[(start, end)]:
				for output in self.cyk_parser.outputs.get((rule_name, (rule1, zero_rule)), []):
					args1 = self._get_output(rule1, start, end, memoize)
					args2 = self.cyk_parser.zero_outputs[zero_rule]
					self._add_two_rule_output(ans, output, args1, args2)

		result = frozenset(ans)

		if memoize:
			self.memoized_outputs[(rule_name, start, end)] = result

		return result

	def _add_two_rule_output(
		self,
		ans: set[OutputT | "DenormalizedArgs[OutputT]"],
		output: NormalizedOutput[OutputT],
		args1: frozenset[OutputT | "DenormalizedArgs[OutputT]" | None] | None,
		args2: frozenset[OutputT | "DenormalizedArgs[OutputT]" | None] | None
	):
		if args1 is None:
			args1 = frozenset({None})

		if args2 is None:
			args2 = frozenset({None})

		assert args1 and args2 and len(args1) > 0 and len(args2) > 0
		for arg1 in args1:
			assert not isinstance(arg1, DenormalizedArgs)
			for arg2 in args2:
				if isinstance(output, grammar.Output):
					assert not isinstance(arg2, DenormalizedArgs)
					ans.add(output.eval([arg for arg in (arg1, arg2) if arg is not None]))

				elif isinstance(output, DenormalizeStartOutput):
					assert not isinstance(arg2, DenormalizedArgs)
					ans.add(output.start_chain(arg1, arg2))

				elif isinstance(output, DenormalizeChainOutput):
					assert isinstance(arg2, DenormalizedArgs)
					ans.add(output.continue_chain(arg1, arg2))

				elif isinstance(output, DenormalizeEndOutput):
					assert isinstance(arg2, DenormalizedArgs)
					ans.add(output.end_chain(arg1, arg2))

	def print(self) -> None:
		try:
			import rich

		except ModuleNotFoundError:
			print(self.cyk_table)
			return

		from rich.table import Table

		size = len(self.tokens)
		table = [[("" if row <= col else "X") for col in range(size)] for row in range(size)]
		for start in range(size):
			for end in range(start+1, size+1):
				table[end-start-1][end-1] = ", ".join(sorted(self.cyk_table[(start, end)]))
		
		rtable = Table(show_lines=True, show_footer=True)
		for token in self.tokens:
			rtable.add_column(token.surfaceform, repr(token))
		for row in reversed(table):
			rtable.add_row(*row)
		
		rich.print(rtable)


class DenormalizedArgs[OutputT](NamedTuple):
	args: tuple[OutputT, ...]


class DenormalizeStartOutput[OutputT]:
	def __init__(self, a_is_nonterminal: bool, b_is_nonterminal: bool):
		self.a_is_nonterminal = a_is_nonterminal
		self.b_is_nonterminal = b_is_nonterminal

	def __repr__(self):
		return "DenormalizeStartOutput()"

	def start_chain(self, a: OutputT | None, b: OutputT | None) -> DenormalizedArgs[OutputT]:
		if self.a_is_nonterminal and self.b_is_nonterminal:
			assert a is not None and b is not None
			return DenormalizedArgs((a, b))
		
		elif self.a_is_nonterminal:
			assert a is not None and b is None
			return DenormalizedArgs((a,))
		
		elif self.b_is_nonterminal:
			assert a is None and b is not None
			return DenormalizedArgs((b,))
		
		else:
			return DenormalizedArgs(())


class DenormalizeChainOutput[OutputT]:
	def __init__(self, a_is_nonterminal: bool):
		self.a_is_nonterminal = a_is_nonterminal

	def __repr__(self):
		return "DenormalizeChainOutput()"

	def continue_chain(self, arg: OutputT | None, args: DenormalizedArgs) -> DenormalizedArgs[OutputT]:
		if self.a_is_nonterminal:
			assert arg is not None
			return DenormalizedArgs((arg,) + args.args)
		
		else:
			assert arg is None
			return args


class DenormalizeEndOutput[OutputT]:
	def __init__(self, a_is_nonterminal: bool, output: grammar.Output[OutputT]):
		self.a_is_nonterminal = a_is_nonterminal
		self.output = output

	def __repr__(self):
		return "DenormalizeEndOutput(" + repr(self.output) + ")"

	def end_chain(self, arg: OutputT | None, args: DenormalizedArgs) -> OutputT:
		if self.a_is_nonterminal:
			assert arg is not None
			args = DenormalizedArgs((arg,) + args.args)
		
		else:
			assert arg is None
			args = args

		return self.output.eval(args.args)
