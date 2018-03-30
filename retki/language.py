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

import readline, os, sys
import itertools
from suomilog.patternparser import ERRORS, setDebug, PatternRef, Grammar
from suomilog.finnish import tokenize, CASES

GRAMMAR = Grammar()
pgl = GRAMMAR.parseGrammarLine

class AnyPattern:
	def __init__(self, allow_empty):
		self.allow_empty = allow_empty
	def __repr__(self):
		return "AnyPattern()"
	def toCode(self):
		return "<pattern that matches all strings without punctuation>"
	def match(self, grammar, tokens, bits):
		for token in tokens:
			if token.token in [".", ",", ":", "!", "?", "[", "]"]:
				return []
		return [[lambda: tokens, " ".join([t.token for t in tokens])]]
	def allowsEmptyContent(self):
		return self.allow_empty

GRAMMAR.patterns["*"] = [
	AnyPattern(False)
]

GRAMMAR.patterns["**"] = [
	AnyPattern(True)
]

class WordPattern:
	def __repr__(self):
		return "WordPattern()"
	def toCode(self):
		return "<pattern that matches any single token>"
	def match(self, grammar, tokens, bits):
		if len(tokens) != 1:
			return []
		return [[lambda: tokens[0], tokens[0].token]]
	def allowsEmptyContent(self):
		return False

GRAMMAR.patterns["."] = [
	WordPattern()
]

class StringContentPattern:
	def __repr__(self):
		return "StringContentPattern()"
	def toCode(self):
		return "<pattern that matches all strings without quote marks>"
	def match(self, grammar, tokens, bits):
		for token in tokens:
			if token.token == '"':
				return []
		string = " ".join([t.token for t in tokens])
		return [[lambda: string, string]]
	def allowsEmptyContent(self):
		return True

GRAMMAR.patterns["STR-CONTENT"] = [
	StringContentPattern()
]

class FuncOutput:
	def __init__(self, f):
		self.func = f
	def eval(self, args):
		return lambda: self.func(*[arg() for arg in args])

identity = FuncOutput(lambda x: x)

def nameToBaseform(tokens, bits, rbits):
	ans = []
	found = False
	for token in reversed(tokens):
		for bf, tbits in token.alternatives:
			if not found:
				if rbits <= tbits:
					ans.append((bf, bits or {"$"}))
					found = True
					break
			else:
				if rbits <= tbits and ("laatusana" in tbits or "nimisana_laatusana" in tbits or "agent" in tbits):
					ans.append((bf, bits or {"$"}))
					break
		else:
			ans.append((token.token, set()))
	return reversed(ans)

def tokensToString(tokens, rbits={"nimento"}):
	return " ".join([text for text, bits in nameToBaseform(tokens, {}, rbits)])

def nameToCode(name, bits=None, rbits={"nimento"}):
	return " ".join([token + ("{" + ",".join(tbits) + "}" if tbits else "") for token, tbits in nameToBaseform(name, bits, rbits)])

def tokensToCode(tokens):
	return " ".join([token.toCode() for token in tokens])

# Luokat

counter = 0

class RObject:
	def __init__(self, rclass):
		self.rclass = rclass
		self.data = {}
		self.extra = {}
	def get(self, field_name):
		if field_name not in self.data:
			self.data[field_name] = self.rclass.fields[field_name].default_value
		return self.data[field_name]
	def set(self, field_name, val):
		self.data[field_name] = val
	def setExtra(self, name, data):
		self.extra[name] = data
		return self
	def asString(self):
		return "[eräs " + self.rclass.name + "]"

class RClass:
	def __init__(self, name, superclass, name_tokens):
		global counter
		counter += 1
		
		self.id = counter
		self.name = name
		self.name_tokens = name_tokens
		self.superclass = superclass
		self.direct_subclasses = []
		self.fields = {}
		
		if superclass:
			self.superclass.direct_subclasses.append(self)
	def newInstance(self):
		return RObject(self)
	def superclasses(self):
		if self.superclass == None:
			return [self]
		else:
			return [self] + self.superclass.superclasses()
	def subclasses(self):
		ans = [self]
		for subclass in self.direct_subclasses:
			ans += subclass.subclasses()
		return ans
	def nameToCode(self, bits):
		if self.name_tokens:
			return nameToCode(name_tokens, rbits={"nimento", "yksikkö"}, bits=bits)
		else:
			return self.name + "{" + ",".join(bits) + "}"
class RField:
	def __init__(self, counter, name, vtype, defa=None):
		self.id = counter
		self.name = name
		self.type = vtype
		self.default_value = defa or ei_mikään
	def copy(self):
		return RField(self.counter, self.name, self.vtype, self.default_value)

class RPattern:
	def __init__(self, rclass=None):
		self.rclass = rclass
	def matches(self, obj):
		if self.rclass:
			if obj.rclass not in self.rclass.subclasses():
				return False
		return True
	def type(self):
		return self.rclass or asia

def defineClass(name, superclass):
	_defineClass(tokensToString(name), nameToCode(name, rbits={"nimento", "yksikkö"}), superclass)
def _defineClass(name_str, name_code, superclass, name_tokens=None):
	rclass = RClass(name_str, superclass, name_tokens)
	for clazz in reversed(superclass.superclasses()) if superclass else []:
		for fname in clazz.fields:
			rclass.fields[fname] = clazz.fields[fname].copy()
	for clazz in rclass.superclasses():
		pgl(".CLASS-%d ::= %s -> %s" % (clazz.id, name_code, name_str), FuncOutput(lambda: rclass))
		pgl(".PATTERN-%d ::= %s -> %s" % (clazz.id, name_code, name_str), FuncOutput(lambda: RPattern(rclass=rclass)))
	pgl(".CLASS ::= %s -> %s" % (name_code, name_str), FuncOutput(lambda: rclass))
	return rclass

pgl(".CLASS-DEF ::= .* on käsite . -> class $1 : asia", FuncOutput(lambda x: defineClass(x, asia)))
pgl(".CLASS-DEF ::= .* on .CLASS{omanto} alakäsite . -> class $1 : $2", FuncOutput(defineClass))
pgl(".DEF ::= .CLASS-DEF -> $1", identity)

# Sisäänrakennetut luokat

asia = _defineClass("asia", "asia{$}", None)

ei_mikään = asia.newInstance()
pgl(".EXPR-%d ::= ei-mikään{$} -> ei-mikään" % (asia.id,), FuncOutput(lambda: ei_mikään))

merkkijono = _defineClass("merkkijono", "merkkijono{$}", asia)
pgl('.EXPR-%d ::= " .STR-CONTENT " -> "$1"' % (merkkijono.id,), FuncOutput(lambda x: merkkijono.newInstance().setExtra("str", x)))

# Ominaisuudet

def defineField(owner, name, vtype, case="nimento"):
	name_str = tokensToString(name, {"yksikkö", case})
	global counter
	counter += 1
	
	for clazz in owner.subclasses():
		field = RField(counter, name_str, vtype)
		clazz.fields[name_str] = field
	
	for clazz in vtype.superclasses():
		pgl(".EXPR-%d ::= .EXPR-%d{omanto} %s -> $1.%s" % (clazz.id, owner.id, nameToCode(name, rbits={case, "yksikkö"}), name_str), FuncOutput(lambda obj: obj.get(name_str)))
	
	def setDefaultValue(clazz, defa):
		clazz.fields[name_str].default_value = defa
	pgl(".FIELD-DEFAULT-DEF-%d ::= .CLASS-%d{omanto} %s on yleensä .EXPR-%d . -> $1.%s defaults $2" % (
		field.id, owner.id, nameToCode(name, {"nimento"}, rbits={case, "yksikkö"}), vtype.id, name_str
	), FuncOutput(setDefaultValue))
	pgl(".DEF ::= .FIELD-DEFAULT-DEF-%d -> $1" % (field.id,), identity)
	
	pgl(".CMD ::= .EXPR-%d{omanto} %s on nyt .EXPR-%d . -> $1.%s = $2" % (
		owner.id, nameToCode(name, {"nimento"}, rbits={case, "yksikkö"}), vtype.id, name
	), FuncOutput(lambda obj, val: obj.set(name_str, val)))

pgl(".FIELD-DEF ::= .CLASS{ulkoolento} on .* , joka on .CLASS{nimento} . -> $1.$2 : $3", FuncOutput(defineField))
pgl(".FIELD-DEF ::= .CLASS{ulkoolento} on .* kutsuttu .CLASS{nimento} . -> $1.$2 : $3", FuncOutput(lambda *x: defineField(*x, case="tulento")))
pgl(".DEF ::= .FIELD-DEF -> $1", identity)

# Muuttujat

class RScope:
	def __init__(self, supers):
		self.variables = {}
		self.superscope = supers
		self.bits = set()
	def bitOn(self, bit):
		self.bits.add(bit)
	def bitOff(self, bit):
		if bit in self.bits:
			self.bits.remove(bit)

SCOPE = [RScope(None)]

def pushScope():
	SCOPE.append(RScope(SCOPE[-1]))
def popScope():
	SCOPE.pop()
def getVar(name):
	for scope in reversed(SCOPE):
		if name in scope.variables:
			return scope.variables[name]
	return None
def setVar(name, val):
	for scope in reversed(SCOPE):
		if name in scope.variables:
			scope.variables[name] = val
			break
	else:
		SCOPE[-1].variables[name] = val

def defineVariable(name, vtype):
	name_str = tokensToString(name)
	SCOPE[-1].variables[name_str] = vtype.newInstance()
	for clazz in vtype.superclasses():
		pgl(".EXPR-%d ::= %s -> %s" % (clazz.id, nameToCode(name, rbits={"yksikkö", "nimento"}), name_str), FuncOutput(lambda: getVar(name_str)))
	pgl(".CMD ::= %s on nyt EXPR-%d . -> %s = $1" % (nameToCode(name, {"nimento"}, rbits={"yksikkö", "nimento"}), vtype.id, name_str), FuncOutput(lambda x: setVar(name_str, x)))

pgl(".VARIABLE-DEF ::= .* on .CLASS{nimento} . -> $1 : $2", FuncOutput(defineVariable))
pgl(".DEF ::= .VARIABLE-DEF -> $1", identity)

# Toiminnot

class RAction:
	def __init__(self, name):
		global counter
		counter += 1
		self.id = counter
		self.name = name
	def run(self, args):
		listeners = []
		for listener in ACTION_LISTENERS:
			if listener.action is self and all([p.matches(obj) for obj, (_, p, _) in zip(args, listener.params)]):
				listeners.append(listener)
		for listener in sorted(listeners, key=lambda l: l.priority):
			listener.run(args)
			if "stop action" in SCOPE[-1].bits:
				break

class RListener:
	def __init__(self, action, params, priority):
		self.action = action
		self.params = params
		self.priority = priority
		self.grammar = GRAMMAR.copy()
	def parse(self, file):
		for c, p, n in self.params:
			self.createParamPhrases(c, p, n)
		self.grammar.parseGrammarLine(".CMD ::= keskeytä toiminto . -> stop", FuncOutput(lambda: SCOPE[-2].bitOn("stop action"))) # suoritetaan isäntäscopessa
		self.body = parseBlock(file, self.grammar)
	def createParamPhrases(self, c, p, n):
		vtype = p.type()
		if n:
			self.grammar.parseGrammarLine(".EXPR-%d ::= %s -> %s param" % (vtype.id, n, vtype.name), FuncOutput(lambda: getVar("_"+c)))
		else:
			self.grammar.parseGrammarLine(".EXPR-%d ::= se{$} -> %s param" % (vtype.id, vtype.name), FuncOutput(lambda: getVar("_"+c)))
	def run(self, args):
		pushScope()
		for (c, _, _), a in zip(self.params, args):
			SCOPE[-1].variables["_"+c] = a
		for cmd in self.body:
			cmd[0]()
		popScope()

LISTENER_PRIORITIES = [
	("ennen", "osanto", "", 20),
	("", "omanto", "aikana", 50),
	("", "omanto", "jälkeen", 50),
]

ACTION_LISTENERS = []

def defineAction(name, params, pre, post):
	action = RAction(name)
	
	def defineActionListener(patterns, priority):
		listener = RListener(action, [(a_case, pattern, name) for (pattern, name), (_, _, a_case) in zip(patterns, params)], priority)
		ACTION_LISTENERS.append(listener)
		return listener
	
	def separateGroups(groups, nameds):
		i = 0
		j = 0
		ans = []
		while i < len(groups):
			if nameds[j]:
				ans.append((groups[i], groups[i+1]))
				i += 2
			else:
				ans.append((groups[i], None))
				i += 1
			j += 1
		return ans
	
	def addListenerDefPattern(p_pre, p_case, p_post, priority, nameds):
		pgl(".LISTENER-DEF-%d ::= %s %s %s %s{-minen,%s} %s %s : -> def %s($1):" % (
			action.id,
			p_pre,
			" ".join([
				"%s .PATTERN-%d{%s,yksikkö}" % (tokensToCode(a_pre), a_class.id, a_case)
				+ (" ( .* )" if named else "")
			for named, (a_pre, a_class, a_case) in zip(nameds, params)]),
			tokensToCode(pre), name.baseform("-minen"), p_case, tokensToCode(post), p_post,
			name.token
		), FuncOutput(lambda *groups: defineActionListener(separateGroups(groups, nameds), priority)))
	
	for p_pre, p_case, p_post, priority in LISTENER_PRIORITIES:
		for nameds in itertools.product(*[[False, True]*len(params)]):
			addListenerDefPattern(p_pre, p_case, p_post, priority, nameds)
	pgl(".DEF ::= .LISTENER-DEF-%d -> $1" % (action.id,), identity)
	
	def defineCommand(cmd_cases, pre, *posts):
		pgl(".CMD ::= %s %s . -> %s($1)" % (
			tokensToCode(pre),
			" ".join([
				".EXPR-%d{%s,yksikkö} %s" % (a_class.id, cmd_case, tokensToCode(post))
			for cmd_case, (_, a_class, _), post in zip(cmd_cases, params, posts)]),
			name.token
		), FuncOutput(lambda val: action.run([val])))
	
	def addCommandDefPhrase(cmd_cases):
		cmd_pattern = " ".join([
				"[ " + a_class.nameToCode({cmd_case, "yksikkö"}) + " .** ]"
			for cmd_case, (_, a_class, _) in zip(cmd_cases, params)])
		pgl(".COMMAND-DEF-%d ::= %s %s %s{-minen,omanto} %s komento on \" .** %s \" . -> def %s command" % (
			action.id,
			" ".join([
				tokensToCode(a_pre) + a_class.nameToCode({a_case, "yksikkö"})
			for a_pre, a_class, a_case in params]),
			tokensToCode(pre), name.baseform("-minen"), tokensToCode(post),
			cmd_pattern,
			name.token
		), FuncOutput(lambda *p: defineCommand(cmd_cases, *p)))
		if sum([len(a_pre) for a_pre, _, _ in params]) + len(pre) + len(post) != 0:
			pgl(".COMMAND-DEF-%d ::= %s %s %s{-minen,omanto} %s komento on \" .** %s \" . -> def %s command" % (
				action.id,
				" ".join([tokensToCode(a_pre) for a_pre, _, _ in params]),
				tokensToCode(pre), name.baseform("-minen"), tokensToCode(post),
				cmd_pattern,
				name.token
			), FuncOutput(lambda *p: defineCommand(cmd_cases, *p)))
		pgl(".COMMAND-DEF-%d ::= %s %s{-minen,omanto} %s komento on \" .** %s \" . -> def %s command" % (
			action.id,
			tokensToCode(pre), name.baseform("-minen"), tokensToCode(post),
			cmd_pattern,
			name.token
		), FuncOutput(lambda *p: defineCommand(cmd_cases, *p)))
	
	for cmd_cases in itertools.product(*[CASES]*len(params)):
		addCommandDefPhrase(cmd_cases)
	
	pgl(".DEF ::= .COMMAND-DEF-%d -> $1" % (action.id,), identity)

def addActionDefPattern(cases):
	def transformArgs(args):
		ans = []
		for case, i in zip(cases, range(0, len(cases)*2, 2)):
			ans.append((args[i], args[i+1], case))
		return args[i+3], ans, args[i+2], args[i+4]
	pgl(".ACTION-DEF ::= %s .** ..{-minen,nimento} .** on toiminto . -> action $%d(%d)" % (
		" ".join([".** [ .CLASS{%s,yksikkö} ]" % (case,) for case in cases]),
		len(cases)*2+2,
		len(cases)
	), FuncOutput(lambda *p: defineAction(*transformArgs(p))))

for i in [0,1,2]:
	for cases in itertools.product(*[CASES]*i):
		addActionDefPattern(cases)

pgl(".DEF ::= .ACTION-DEF -> $1", identity)

# Tulostaminen

def printCommand(value):
	if value.rclass is merkkijono:
		print(value.extra["str"])
	else:
		print(value.asString())

pgl(".CMD ::= sano .EXPR-%d{nimento} . -> print($1)" % (asia.id,), FuncOutput(printCommand))

# Komentojen jäsentäminen

def parseBlock(file, grammar):
	ans = []
	while True:
		line = file.readline()
		if not line.strip():
			break
		alternatives = grammar.matchAll(tokenize(line.strip()), "CMD", set())
		if len(alternatives) != 1:
			sys.stderr.write("Virhe jäsennettäessä riviä `" + line.strip() + "'. Vaihtoehdot: " + ", ".join([a[1] for a in alternatives]))
			break
		ans.append(alternatives[0])
	return ans

# Pääohjelma

def main():
	def complete_file(t, s):
		path, file = os.path.split(t)
		alternatives = []
		try:
			for c in sorted(["/kielioppi", "/käsitteet", "/debug", "/virheet", "/match", "/eval", "/lataa"]):
				if c.startswith(t):
					alternatives.append(c)
			for f in filter(lambda f: f.startswith(file), os.listdir(path or ".")):
				alt = os.path.join(path, f)
				if os.path.isdir(alt):
					alternatives.append(os.path.join(alt, ""))
				else:
					alternatives.append(alt)
			return alternatives[s] if s < len(alternatives) else None
		except Exception as e:
			print(e)
	readline.set_completer(complete_file)
	readline.set_completer_delims(" ")
	readline.parse_and_bind('tab: complete')
	
	def printGrammar(grammar):
		for category in sorted(grammar.patterns):
			print(category, "::=")
			for pattern in grammar.patterns[category]:
				print(" " + pattern.toCode())
	
	def printStatistics():
		n_patterns = sum([len(category) for category in GRAMMAR.patterns.values()])
		print("Ladattu", n_patterns, "fraasia.")
	
	printStatistics()
	while True:
		try:
			line = input(">> ")
		except EOFError:
			break
		if not line:
			continue
		if line == "/kielioppi":
			printGrammar(GRAMMAR)
			continue
		elif line == "/käsitteet":
			def printClass(clazz, indent):
				print(" "*indent + clazz.name + "{" + ", ".join(sorted(clazz.fields.keys())) + "}")
				for subclass in sorted(clazz.direct_subclasses, key=lambda c: c.name):
					printClass(subclass, indent+1)
			printClass(asia, 0)
			continue
		elif line == "/debug 0":
			setDebug(0)
			continue
		elif line == "/debug 1":
			setDebug(1)
			continue
		elif line == "/debug 2":
			setDebug(2)
			continue
		elif line == "/debug 3":
			setDebug(3)
			continue
		elif line == "/virheet":
			if len(ERRORS) > 0:
				print("Mahdollisia virheitä:")
				for error in ERRORS:
					print(error+"\n")
			else:
				print("Ei virheitä.")
			continue
		elif line.startswith("/match"):
			args = line[6:].strip()
			cat = args[:args.index(" ")]
			expr = args[args.index(" ")+1:]
			ints = matchAll(tokenize(expr), cat, set())
			for _, string in ints:
				print(string)
			continue
		elif line.startswith("/eval"):
			print(eval(line[5:].strip()))
			continue
		elif line.startswith("/lataa"):
			file = line[6:].strip()
			with open(file, "r") as f:
				while True:
					l = f.readline()
					if not l:
						break
					if not l.strip():
						continue
					a = GRAMMAR.matchAll(tokenize(l.strip()), "DEF", set())
					if len(a) == 1:
						t = a[0][0]()
						if a[0][1][-1] == ":":
							t.parse(f)
					else:
						print("Virhe jäsennettäessä tiedoston riviä `" + l.strip() + "'.")
			printStatistics()
			continue
		del ERRORS[:]
		phrase_type = "DEF"
		if line[0] == "!":
			phrase_type = "CMD"
			line = line[1:]
		interpretations = GRAMMAR.matchAll(tokenize(line), phrase_type, set())
		if len(interpretations) == 0:
			print("Ei tulkintaa.")
		elif len(interpretations) == 1:
			print(interpretations[0][1])
			interpretations[0][0]()
		else:
			print("Löydetty", len(interpretations), "tulkintaa:")
			for _, interpretation in interpretations:
				print(interpretation)
		printStatistics()
			

if __name__ == "__main__":
	main()
