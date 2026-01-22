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
from . import grammar


type CYKTable = defaultdict[tuple[int, int], set[str]]
type SplitTable = defaultdict[tuple[int, int, str], set[int]]
type TokenOutputTable[OutputT] = defaultdict[tuple[int, int, str], set[OutputT]]


class CYKParser[OutputT]:
	token_rules: dict[str, grammar.Terminal | grammar.BaseRule[OutputT]]
	one_rules: defaultdict[str, set[str]]
	one_rules_expanded: defaultdict[str, set[str]]
	two_rules: defaultdict[tuple[str, str], set[str]]
	outputs: dict[tuple[str, str | tuple[str, str]], grammar.Output[OutputT] | "DenormalizeStartOutput" | "DenormalizeChainOutput" | "DenormalizeEndOutput[OutputT]"]

	def __init__(self, grammar: grammar.Grammar[OutputT], root_nonterminal_name: str):
		self.token_rules = {}
		self.one_rules = defaultdict(set)
		self.one_rules_expanded = defaultdict(set)
		self.two_rules = defaultdict(set)
		self.outputs = {}
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
						if isinstance(word, grammar.BaseformTerminal) or isinstance(word, grammar.SurfaceformTerminal):
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
						assert (nonterminal_name, new_words[0]) not in self.outputs
						self.outputs[(nonterminal_name, new_words[0])] = rule.output
					
					else:
						prev = nonterminal_name
						j = id(rule)
						for i in range(len(new_words)-2):
							next = f"{nonterminal_name}_{j}_CONT{i}"
							pair = (new_words[i], next)
							self.two_rules[pair].add(prev)
							assert (prev, pair) not in self.outputs
							self.outputs[(prev, pair)] = DenormalizeChainOutput(is_nonterminal[i]) if i != 0 else DenormalizeEndOutput(is_nonterminal[i], rule.output)
							prev = next
						
						pair = (new_words[-2], new_words[-1])
						self.two_rules[pair].add(prev)
						assert (prev, pair) not in self.outputs, f"{prev}, {pair}"
						self.outputs[(prev, pair)] = DenormalizeStartOutput(is_nonterminal[-2], is_nonterminal[-1]) if len(new_words) > 2 else rule.output

				else:
					# Oma sääntö.
					# TODO: Tue muita kuin yhden saneen jäsentäviä omia sääntöjä.
					self.token_rules[nonterminal_name] = rule
		
		for a, b in list(self.one_rules.items()):
			self.one_rules_expanded[a] = set(b)
			queue = list(b)
			while queue:
				rule_name = queue.pop()
				for rule in self.one_rules[rule_name]:
					if rule not in self.one_rules_expanded[a]:
						self.one_rules_expanded[a].add(rule)
						queue.append(rule)
	
	def parse(self, tokens: list[grammar.Token]) -> "CYKAnalysis[OutputT]":
		cyk_table: CYKTable = defaultdict(set)
		split_table: SplitTable = defaultdict(set)
		token_outputs: TokenOutputTable = defaultdict(set)
		for i in range(len(tokens)):
			for rule_name, token_rule in self.token_rules.items():
				if isinstance(token_rule, grammar.BaseRule):
					if token_output := token_rule.match(self.grammar, tokens[i:i+1], set()):
						cyk_table[(i, i+1)] |= {rule_name} | self.one_rules_expanded[rule_name]
						token_outputs[(i, i+1, rule_name)] |= set(token_output)
					
				elif token_rule.matches_token(tokens[i]):
					cyk_table[(i, i+1)] |= {rule_name} | self.one_rules_expanded[rule_name]
		
		for span in range(2, len(tokens)+1):
			for start in range(len(tokens)-span+1):
				end = start + span
				for split in range(start+1, end):
					for rule1 in cyk_table[(start, split)]:
						for rule2 in cyk_table[(split, end)]:
							for rule_name in self.two_rules[(rule1, rule2)]:
								cyk_table[(start, end)] |= {rule_name} | self.one_rules_expanded[rule_name]
								split_table[(start, end, rule_name)] |= {split}
		
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
		
		print("Expanded one rules:")
		for a, B in self.one_rules_expanded.items():
			print(B, "<-", a)
		
		print("Outputs:")
		for a, b in self.outputs.items():
			print(repr(a), repr(b))


class CYKAnalysis[OutputT]:
	def __init__(self, cyk_parser: CYKParser[OutputT], tokens: list[grammar.Token], cyk_table: CYKTable, split_table: SplitTable, token_outputs: TokenOutputTable):
		self.cyk_parser = cyk_parser
		self.tokens = tokens
		self.cyk_table = cyk_table
		self.split_table = split_table
		self.token_outputs = token_outputs
	
	def get_output(self, rule_name: str, start: int = 0, end: int = 0) -> set[OutputT] | None:
		if end <= 0:
			end = len(self.tokens) - end

		if rule_name not in self.cyk_table[(start, end)]:
			return None
		
		ans = set()
		if token_output := self.token_outputs.get((start, end, rule_name), None):
			ans |= token_output

		for rule in self.cyk_table[(start, end)]:
			if output := self.cyk_parser.outputs.get((rule_name, rule), None):
				args = self.get_output(rule, start, end)
				assert args is not None
				for arg in args:
					ans.add(output.eval([arg]))

		for split in self.split_table[(start, end, rule_name)]:
			for rule1 in self.cyk_table[(start, split)]:
				for rule2 in self.cyk_table[(split, end)]:
					if output := self.cyk_parser.outputs.get((rule_name, (rule1, rule2)), None):
						args1 = self.get_output(rule1, start, split)
						args2 = self.get_output(rule2, split, end)
						assert args1 and args2 and len(args1) > 0 and len(args2) > 0
						for arg1 in args1:
							for arg2 in args2:
								ans.add(output.eval([arg1, arg2]))
		
		if not ans:
			return None
		
		return ans

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


class DenormalizeStartOutput:
	def __init__(self, a_is_nonterminal: bool, b_is_nonterminal: bool):
		self.a_is_nonterminal = a_is_nonterminal
		self.b_is_nonterminal = b_is_nonterminal

	def __repr__(self):
		return "DenormalizeStartOutput()"

	def eval(self, args):
		assert len(args) == 2
		if self.a_is_nonterminal and self.b_is_nonterminal:
			return (args[0], args[1])
		
		elif self.a_is_nonterminal:
			return (args[0],)
		
		elif self.b_is_nonterminal:
			return (args[1],)
		
		else:
			return ()


class DenormalizeChainOutput:
	def __init__(self, a_is_nonterminal: bool):
		self.a_is_nonterminal = a_is_nonterminal

	def __repr__(self):
		return "DenormalizeChainOutput()"

	def eval(self, args):
		assert len(args) == 2
		if self.a_is_nonterminal:
			return (args[0],) + args[1]
		
		else:
			return args[1]


class DenormalizeEndOutput[OutputT]:
	def __init__(self, a_is_nonterminal: bool, output: grammar.Output[OutputT]):
		self.a_is_nonterminal = a_is_nonterminal
		self.output = output

	def __repr__(self):
		return "DenormalizeEndOutput(" + repr(self.output) + ")"

	def eval(self, args):
		assert len(args) == 2
		if self.a_is_nonterminal:
			args = (args[0],) + args[1]
		
		else:
			args = args[1]

		return self.output.eval(args)