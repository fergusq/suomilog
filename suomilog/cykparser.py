from collections import defaultdict
from typing import List

from . import patternparser as pp


class CYKParser:
	def __init__(self, grammar: pp.Grammar, root_category: str):
		self.token_rules = {}
		self.one_rules = defaultdict(set)
		self.one_rules_expanded = defaultdict(set)
		self.two_rules = defaultdict(set)
		self.outputs = {}
		self.grammar = grammar
		self._toCNF(root_category)
	def _toCNF(self, root_category: str):
		eg = self.grammar.expandBits(root_category, set())
		for category in eg:
			for pattern in eg[category]:
				if isinstance(pattern, pp.Pattern):
					new_words = []
					is_pattern = []
					for word in pattern.words:
						if isinstance(word, pp.Token):
							self.token_rules[word.toCode()] = word
							new_words.append(word.toCode())
							is_pattern.append(False)
						
						elif isinstance(word, pp.PatternRef):
							new_words.append(word.name)
							is_pattern.append(True)
						
						else:
							assert False
					
					if len(new_words) == 1:
						self.one_rules[new_words[0]].add(category)
						assert (category, new_words[0]) not in self.outputs
						self.outputs[(category, new_words[0])] = pattern.output
					
					else:
						prev = category
						j = id(pattern)
						for i in range(len(new_words)-2):
							next = f"{category}_{j}_CONT{i}"
							pair = (new_words[i], next)
							self.two_rules[pair].add(prev)
							assert (prev, pair) not in self.outputs
							self.outputs[(prev, pair)] = DenormalizeChainOutput(is_pattern[i]) if i != 0 else DenormalizeEndOutput(is_pattern[i], pattern.output)
							prev = next
						
						pair = (new_words[-2], new_words[-1])
						self.two_rules[pair].add(prev)
						assert (prev, pair) not in self.outputs, f"{prev}, {pair}"
						self.outputs[(prev, pair)] = DenormalizeStartOutput(is_pattern[-2], is_pattern[-1]) if len(new_words) > 2 else pattern.output

				else:
					self.token_rules[category] = pattern
		
		for a, b in list(self.one_rules.items()):
			self.one_rules_expanded[a] = set(b)
			queue = list(b)
			while queue:
				rule_name = queue.pop()
				for rule in self.one_rules[rule_name]:
					if rule not in self.one_rules_expanded[a]:
						self.one_rules_expanded[a].add(rule)
						queue.append(rule)
	
	def parse(self, tokens: List[pp.Token]):
		cyk_table = defaultdict(set)
		split_table = defaultdict(set)
		for i in range(len(tokens)):
			for rule_name, token_rule in self.token_rules.items():
				if isinstance(token_rule, pp.Token):
					if tokens[i].token == token_rule.token or tokens[i].containsMatch(token_rule.toAlternatives(set())):
						cyk_table[(i, i+1)] |= {rule_name} | self.one_rules_expanded[rule_name]
				
				elif token_rule.match(self.grammar, tokens[i:i+1], set()):
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
		
		return cyk_table, split_table
	
	def getOutput(self, tokens, cyk_table, split_table, start, end, rule_name):
		ans = set()
		for rule in cyk_table[(start, end)]:
			if (rule_name, rule) in self.outputs:
				output = self.outputs[(rule_name, rule)]
				args = self.getOutput(tokens, cyk_table, split_table, start, end, rule)
				assert len(args) > 0
				for arg in args:
					ans.add(output.eval([arg]))

		for split in split_table[(start, end, rule_name)]:
			for rule1 in cyk_table[(start, split)]:
				for rule2 in cyk_table[(split, end)]:
					if (rule_name, (rule1, rule2)) in self.outputs:
						output = self.outputs[(rule_name, (rule1, rule2))]
						args1 = self.getOutput(tokens, cyk_table, split_table, start, split, rule1)
						args2 = self.getOutput(tokens, cyk_table, split_table, split, end, rule2)
						assert len(args1) > 0 and len(args2) > 0
						for arg1 in args1:
							for arg2 in args2:
								ans.add(output.eval([arg1, arg2]))
		
		if not ans:
			return [tokens[start].token]
		
		return ans
	
	def print(self):
		for a, b in self.token_rules.items():
			print(a, "<-", b.toCode())
		
		for a, B in self.one_rules.items():
			for b in sorted(B):
				print(b, "<-", a)
		
		for (a, b), C in self.two_rules.items():
			for c in sorted(C):
				print(c, "<-", a, b)
		
		for a, B in self.one_rules_expanded.items():
			print(B, "<-", a)
		
		for a, b in self.outputs.items():
			print(repr(a), repr(b))

class DenormalizeStartOutput(pp.Output):
	def __init__(self, a_is_pattern: bool, b_is_pattern: bool):
		self.a_is_pattern = a_is_pattern
		self.b_is_pattern = b_is_pattern
	def __repr__(self):
		return "DenormalizeStartOutput()"
	def eval(self, args):
		assert len(args) == 2
		if self.a_is_pattern and self.b_is_pattern:
			return (args[0], args[1])
		
		elif self.a_is_pattern:
			return (args[0],)
		
		elif self.b_is_pattern:
			return (args[1],)
		
		else:
			return ()

class DenormalizeChainOutput(pp.Output):
	def __init__(self, a_is_pattern: bool):
		self.a_is_pattern = a_is_pattern
	def __repr__(self):
		return "DenormalizeChainOutput()"
	def eval(self, args):
		assert len(args) == 2
		if self.a_is_pattern:
			return (args[0],) + args[1]
		
		else:
			return args[1]

class DenormalizeEndOutput(pp.Output):
	def __init__(self, a_is_pattern: bool, output):
		self.a_is_pattern = a_is_pattern
		self.output = output
	def __repr__(self):
		return "DenormalizeEndOutput(" + repr(self.output) + ")"
	def eval(self, args):
		assert len(args) == 2
		if self.a_is_pattern:
			args = (args[0],) + args[1]
		
		else:
			args = args[1]

		return self.output.eval(args)