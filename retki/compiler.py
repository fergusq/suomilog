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

# Villikortit

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
		if len(tokens) != 1 or not any(altbits >= bits for _, altbits in tokens[0].alternatives):
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
		string = ""
		subs = []
		current_subs = None
		for token in tokens:
			if current_subs is not None:
				if token.token == "]":
					string += "%s"
					alts = grammar.matchAll(current_subs, "EXPR-"+str(merkkijono.id), set())
					subs.append(alts)
					current_subs = None
				else:
					current_subs.append(token)
				continue
			if token.token == "[":
				current_subs = []
			elif token.token in [".", ",", ";", "?", "!"]:
				string += token.token
			elif token.token == "%":
				string += " %%"
			else:
				string += " " + token.token
		string = string.strip()
		ans = []
		for alternative in itertools.product(*subs):
			ans.append([
				lambda: string % tuple([p[0]().extra["str"] for p in alternative]),
				string % tuple([p[1] for p in alternative])
			])
		return ans
	def allowsEmptyContent(self):
		return True

GRAMMAR.patterns["STR-CONTENT"] = [
	StringContentPattern()
]

# Ulostulo

class FuncOutput:
	def __init__(self, f):
		self.func = f
	def eval(self, args):
		return lambda: self.func(*[arg() for arg in args])

identity = FuncOutput(lambda x: x)

# Apufunktiot

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
				if rbits <= tbits and tbits & {"laatusana", "nimisana_laatusana", "agent", "asemosana"}:
					ans.append((bf, bits or {"$"}))
					break
		else:
			ans.append((token.token, set()))
	return reversed(ans)

def tokensToString(tokens, rbits={"nimento", "yksikkö"}):
	return " ".join([text for text, bits in nameToBaseform(tokens, {}, rbits)])

def nameToCode(name, bits=None, rbits={"nimento", "yksikkö"}):
	return " ".join([token + ("{" + ",".join(tbits) + "}" if tbits else "") for token, tbits in nameToBaseform(name, bits, rbits)])

def tokensToCode(tokens):
	return " ".join([token.toCode() for token in tokens])

# Bittiluokka

class Bits:
	def __init__(self):
		self.bits = set()
	def bitOn(self, bit):
		self.bits.add(bit)
		return self
	def bitOff(self, bit):
		if bit in self.bits:
			self.bits.remove(bit)
		return self
	def bitsOff(self, bits):
		for bit in bits:
			self.bitOff(bit)
		return self

# Luokat

counter = 0

class RObject(Bits):
	def __init__(self, rclass, name, bits=set()):
		Bits.__init__(self)
		self.rclass = rclass
		self.data = {}
		self.extra = {}
		self.bits.update(bits)
		self.name = name
		if name:
			self.data["nimi koodissa"] = merkkijono.newInstance().setExtra("str", name)
	def get(self, field_name):
		if field_name not in self.data:
			for clazz in self.rclass.superclasses():
				if field_name in clazz.fields and clazz.fields[field_name]:
					self.data[field_name] = clazz.fields[field_name].default_value
					break
			else:
				self.data[field_name] = ei_mikään
		return self.data[field_name]
	def set(self, field_name, val):
		self.data[field_name] = val
	def getMap(self, field_name, key_val):
		key = key_val.toKey()
		if field_name not in self.data:
			self.data[field_name] = {}
		if key not in self.data[field_name]:
			for clazz in self.rclass.superclasses():
				if field_name in clazz.fields and clazz.fields[field_name]:
					return clazz.fields[field_name].default_value
			return ei_mikään
		return self.data[field_name][key]
	def setMap(self, field_name, key_val, val):
		key = key_val.toKey()
		if field_name not in self.data:
			self.data[field_name] = {}
		self.data[field_name][key] = val
	def setExtra(self, name, data):
		self.extra[name] = data
		return self
	def asString(self):
		if self.name:
			return self.name
		if "str" in self.extra:
			return self.extra["str"]
		return "[eräs " + self.rclass.name + "]"
	def toKey(self):
		if "str" in self.extra:
			return self.extra["str"]
		else:
			return self

class RClass(Bits):
	def __init__(self, name, superclass, name_tokens):
		Bits.__init__(self)
		global counter
		counter += 1
		
		self.id = counter
		self.name = name
		self.name_tokens = name_tokens
		self.superclass = superclass
		self.direct_subclasses = []
		self.fields = {}
		self.bit_groups = []
		
		if superclass:
			self.superclass.direct_subclasses.append(self)
	def addField(self, name, field):
		self.fields[name] = field
	def newInstance(self, name=None, bits=set()):
		return RObject(self, name, self.allBits()|bits)
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
	def allBits(self):
		ans = set()
		for clazz in self.superclasses():
			ans.update(clazz.bits)
		return ans
	def nameToCode(self, bits):
		if self.name_tokens:
			return nameToCode(self.name_tokens, rbits={"nimento", "yksikkö"}, bits=bits)
		else:
			return self.name + "{" + ",".join(bits) + "}"
class RField:
	def __init__(self, counter, name, vtype, defa=None, is_map=False):
		self.id = counter
		self.name = name
		self.type = vtype
		self.is_map = is_map
		self.default_value = defa
	def setDefaultValue(self, defa):
		self.default_value = defa
	def copy(self):
		return RField(self.id, self.name, self.type, None, self.is_map)

class RPattern(Bits):
	def __init__(self, rclass=None):
		Bits.__init__(self)
		self.rclass = rclass
	def matches(self, obj):
		if self.rclass:
			if obj.rclass not in self.rclass.subclasses():
				return False
		return obj.bits >= self.bits
	def type(self):
		return self.rclass or asia

CLASSES = {}

def defineClass(name, superclass):
	name_str = tokensToString(name)
	name_code = nameToCode(name)
	
	if name_str in CLASSES:
		raise Exception("redefinition of class " + name_str)
	
	rclass = RClass(name_str, superclass, name)
	CLASSES[name_str] = rclass
	
	for clazz in reversed(superclass.superclasses()) if superclass else []:
		for fname in clazz.fields:
			rclass.fields[fname] = clazz.fields[fname].copy()
	
	pgl(".CLASS-PATTERN-%d ::= %s -> %s" % (rclass.id, name_code, name_str), FuncOutput(lambda: RPattern(rclass=rclass)))
	pgl(".CLASS-PATTERN ::= .CLASS-PATTERN-%d{$} -> $1" % (rclass.id,), identity)
	for clazz in rclass.superclasses():
		pgl(".CLASS-%d ::= %s -> %s" % (clazz.id, name_code, name_str), FuncOutput(lambda: rclass))
		pgl(".PATTERN-%d ::= %s -> %s" % (clazz.id, name_code, name_str), FuncOutput(lambda: RPattern(rclass=rclass)))
		if clazz is not rclass:
			for _, group_strs, group_codes in clazz.bit_groups:
				for group_str, group_code in zip(group_strs, group_codes):
					addBitPhrase(rclass, group_str, group_code, group_strs)
	pgl(".CLASS ::= %s -> %s" % (name_code, name_str), FuncOutput(lambda: rclass))
	
	def addMapFieldDefPattern(key_case, is_pre):
		pgl(".DEF ::= Kutakin %s kohden .CLASS{ulkoolento} voi olla %s se{%s} %s %s kutsuttu .CLASS{nimento} . -> $1.$2 : {$4}" % (
			nameToCode(name, bits={"osanto", "yksikkö"}),
			".**" if is_pre else "",
			key_case,
			nameToCode(name, bits={key_case, "yksikkö"}),
			".**" if not is_pre else ""
		), FuncOutput(lambda *p: defineMapField(rclass, key_case, is_pre, *p, case="tulento")))
	
	for key_case in CASES:
		for is_pre in [True, False]:
			addMapFieldDefPattern(key_case, is_pre)
	
	return rclass

pgl(".CLASS-DEF ::= .* on käsite . -> class $1 : asia", FuncOutput(lambda x: defineClass(x, asia)))
pgl(".CLASS-DEF ::= .* on .CLASS{omanto} alakäsite . -> class $1 : $2", FuncOutput(defineClass))
pgl(".DEF ::= .CLASS-DEF -> $1", identity)

# Ominaisuudet

def definePolyparamField(field_id, owner, vtype, to_register, pattern, to_get, get_str_output, to_set, set_str_output, defa_pattern, to_set_defa, set_defa_str_output):
	
	for clazz in owner.subclasses():
		to_register(clazz)
	
	for clazz in vtype.superclasses():
		pgl(".EXPR-%d ::= .EXPR-%d{omanto} %s -> %s" % (clazz.id, owner.id, pattern({"$"}), get_str_output), FuncOutput(to_get))
	
	pgl(".FIELD-DEFAULT-DEF-%d ::= .CLASS-%d{omanto} %s on yleensä .EXPR-%d . -> %s" % (
		field_id, owner.id, defa_pattern({"yksikkö", "nimento"}), vtype.id, set_defa_str_output
	), FuncOutput(to_set_defa))
	pgl(".DEF ::= .FIELD-DEFAULT-DEF-%d -> $1" % (field_id,), identity)
	
	pgl(".FIELD-VALUE-DEF-%d ::= .EXPR-%d{omanto} %s on .EXPR-%d . -> %s" % (
		field_id, owner.id, pattern({"yksikkö", "nimento"}), vtype.id, set_str_output
	), FuncOutput(to_set))
	pgl(".DEF ::= .FIELD-VALUE-DEF-%d -> $1" % (field_id,), identity)
	
	pgl(".CMD ::= .EXPR-%d{omanto} %s on nyt .EXPR-%d . -> %s" % (
		owner.id, pattern({"yksikkö", "nimento"}), vtype.id, set_str_output
	), FuncOutput(to_set))

def defineField(owner, name, vtype, case="nimento"):
	name_str = tokensToString(name, {"yksikkö", case})
	global counter
	counter += 1
	
	pattern = lambda bits: nameToCode(name, bits, rbits={case, "yksikkö"})
	
	definePolyparamField(
		counter,
		owner,
		vtype,
		lambda clazz: clazz.addField(name_str, RField(counter, name_str, vtype)),
		pattern,
		lambda obj: obj.get(name_str),
		"$1.%s" % (name_str,),
		lambda obj, val: obj.set(name_str, val),
		"$1.%s = $2" % (name_str,),
		pattern,
		lambda clazz, defa: clazz.fields[name_str].setDefaultValue(defa),
		"$1.%s defaults $2" % (name_str,)
	)

pgl(".FIELD-DEF ::= .CLASS{ulkoolento} on .* , joka on .CLASS{nimento} . -> $1.$2 : $3", FuncOutput(defineField))
pgl(".FIELD-DEF ::= .CLASS{ulkoolento} on .* kutsuttu .CLASS{nimento} . -> $1.$2 : $3", FuncOutput(lambda *x: defineField(*x, case="tulento")))
pgl(".DEF ::= .FIELD-DEF -> $1", identity)

def defineMapField(key_class, key_case, is_pre, owner, name, vtype, case="nimento"):
	name_str = "m"+str(key_class.id)+"-"+tokensToString(name, rbits={case, "yksikkö"})
	name_code = nameToCode(name, rbits={case, "yksikkö"})
	
	global counter
	counter += 1
	
	def createKeyPattern(category):
		return ".%s-%d{%s}" % (category, key_class.id, key_case)
	pre = lambda cat: (createKeyPattern(cat)+" " if not is_pre else "")
	post = lambda cat: (" "+createKeyPattern(cat) if is_pre else "")
	
	definePolyparamField(
		counter,
		owner,
		vtype,
		lambda clazz: clazz.addField(name_str, RField(counter, name_str, vtype, is_map=True)),
		lambda bits: pre("EXPR") + nameToCode(name, bits, rbits={case, "yksikkö"}) + post("EXPR"),
		lambda obj, key: obj.getMap(name_str, key),
		"$1.%s" % (name_str,),
		lambda obj, key, val: obj.setMap(name_str, key, val),
		"$1.%s = $2" % (name_str,),
		lambda bits: pre("CLASS") + nameToCode(name, bits, rbits={case, "yksikkö"}) + post("CLASS"),
		lambda clazz, _, defa: clazz.fields[name_str].setDefaultValue(defa),
		"$1.%s defaults $2" % (name_str,)
	)

# Adjektiivit

def addBitPhrase(clazz, name_code, name_str, name_strs):
	pgl(".PATTERN-%d ::= %s .PATTERN-%d{$} -> %s($1)" % (clazz.id, name_code, clazz.id, name_str),
		FuncOutput(lambda p: p.bitsOff(name_strs).bitOn(name_str)))
	pgl(".CLASS-PATTERN-%d ::= %s .PATTERN-%d{$} -> %s($1)" % (clazz.id, name_code, clazz.id, name_str),
		FuncOutput(lambda p: p.bitsOff(name_strs).bitOn(name_str)))

def defineBit(owner, *names):
	global counter
	counter += 1
	names = names
	name_strs = []
	name_codes = []
	for name in names:
		name_strs.append(tokensToString(name, {"yksikkö", "nimento"}))
		name_codes.append(nameToCode(name, rbits={"yksikkö", "nimento"}))
	owner.bit_groups.append((names, name_strs, name_codes))
	def addBitPhrases(name, name_str, name_code):
		name_code_nominative = nameToCode(name, bits={"yksikkö", "nimento"}, rbits={"yksikkö", "nimento"})
		
		pgl(".ENUM-DEFAULT-DEF-%d ::= .CLASS-%d{nimento} on yleensä %s . -> $1 defaults %s" % (
			counter, owner.id, name_code_nominative, name_str
		), FuncOutput(lambda c: c.bitOn(name_str)))

		for clazz in owner.subclasses():
			addBitPhrase(clazz, name_code, name_str, name_strs)
		
		pgl(".CMD ::= .EXPR-%d{nimento} on nyt %s . -> $1.%s = True" % (
			owner.id, name_code_nominative, name_str
		), FuncOutput(lambda obj: obj.bitsOff(name_strs).bitOn(name_str)))
		
		# TODO
		pgl(".COND ::= .EXPR-%d{nimento} on %s -> $1.%s" %(
			owner.id, name_code_nominative, name_str
		), FuncOutput(lambda obj: name_str in obj.bits))
		
	for name, name_str, name_code in zip(names, name_strs, name_codes):
		addBitPhrases(name, name_str, name_code)
	pgl(".DEF ::= .ENUM-DEFAULT-DEF-%d -> $1" % (counter,), identity)

pgl(".ENUM-DEF ::= .CLASS{nimento} voi olla .* . -> $1 has bit $2", FuncOutput(defineBit))
pgl(".ENUM-DEF ::= .CLASS{nimento} on joko .* tai .* . -> $1 has bits $2==!$3", FuncOutput(defineBit))
pgl(".ENUM-DEF ::= .CLASS{nimento} on joko .* , .* tai .* . -> $1 has bits $2==!($3|$4)", FuncOutput(defineBit))
pgl(".DEF ::= .ENUM-DEF -> $1", identity)

# Relaatiot

def defineRelation(symmetric, name, rclass1, rclass2):
	pass #TODO

pgl(".RELATION-DEF ::= .* on .CLASS{omanto} ja .CLASS{omanto} välinen relaatio. -> relation $1 : $2 <-> $3", FuncOutput(lambda *p: defineRelation(True, *p)))
pgl(".RELATION-DEF ::= .* on .CLASS{omanto} ja .CLASS{omanto} välinen suunnattu relaatio. -> relation $1 : $2 <-> $3", FuncOutput(lambda *p: defineRelation(False, *p)))
pgl(".DEF ::= .RELATION-DEF -> $1", identity)

# Muuttujat

class RScope(Bits):
	def __init__(self):
		Bits.__init__(self)
		self.variables = {}
	def __repr__(self):
		return "Scope(" + repr(self.variables) + ")"

GLOBAL_SCOPE = RScope()
SCOPE = []
STACK = []

def pushScope():
	SCOPE.append(RScope())
def popScope():
	SCOPE.pop()
def pushStackFrame():
	STACK.append(RScope())
def popStackFrame():
	STACK.pop()
def visibleScopes():
	return [GLOBAL_SCOPE]+SCOPE+STACK[-1:]
def getVar(name):
	for scope in reversed(visibleScopes()):
		if name in scope.variables:
			return scope.variables[name]
	sys.stderr.write("Muuttujaa ei löytynyt: " + name + "(" + repr(visibleScopes()) + ")\n")
	return ei_mikään
def setVar(name, val):
	scopes = visibleScopes()
	for scope in reversed(scopes):
		if name in scope.variables:
			scope.variables[name] = val
			break
	else:
		scopes[-1].variables[name] = val
def putVar(name, val):
	visibleScopes()[-1].variables[name] = val

def defineVariable(name, pattern):
	name_str = tokensToString(name)
	vtype = pattern.type()
	GLOBAL_SCOPE.variables[name_str] = vtype.newInstance(name_str, bits=pattern.bits)
	for clazz in vtype.superclasses():
		pgl(".EXPR-%d ::= %s -> %s" % (clazz.id, nameToCode(name, rbits={"yksikkö", "nimento"}), name_str), FuncOutput(lambda: getVar(name_str)))
	pgl(".CMD ::= %s on nyt EXPR-%d . -> %s = $1" % (nameToCode(name, {"nimento"}, rbits={"yksikkö", "nimento"}), vtype.id, name_str), FuncOutput(lambda x: setVar(name_str, x)))

pgl(".VARIABLE-DEF ::= .* on .CLASS-PATTERN{nimento} . -> $1 : $2", FuncOutput(defineVariable))
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
		pushScope()
		scope = SCOPE[-1]
		special_case_found = False
		for listener in sorted(listeners, key=lambda l: l.priority):
			if listener.is_general_case and special_case_found:
				continue
			if listener.is_special_case:
				special_case_found = True
			listener.run(args)
			if "stop action" in scope.bits:
				break
		popScope()

class RListener:
	def __init__(self, action, params, priority, is_special_case, is_general_case):
		self.action = action
		self.params = params
		self.priority = priority
		self.is_special_case = is_special_case
		self.is_general_case = is_general_case
		self.grammar = GRAMMAR.copy()
	def parse(self, file):
		for c, p, n in self.params:
			self.createParamPhrases(c, p, n)
		self.grammar.parseGrammarLine(".CMD ::= keskeytä toiminto . -> stop", FuncOutput(lambda: SCOPE[-1].bitOn("stop action"))) # suoritetaan isäntäscopessa
		self.body = parseBlock(file, self.grammar)
	def createParamPhrases(self, c, p, n):
		vtype = p.type()
		if n:
			for clazz in vtype.superclasses():
				self.grammar.parseGrammarLine(".EXPR-%d ::= %s -> %s param" % (
					clazz.id, nameToCode(n, rbits={"yksikkö", "nimento"}), vtype.name
				), FuncOutput(lambda: getVar("_"+c)))
		else:
			pronoun = "hän" if "inhimillinen" in vtype.bits else "se"
			for clazz in vtype.superclasses():
				self.grammar.parseGrammarLine(".EXPR-%d ::= %s{$} -> %s param" % (clazz.id, pronoun, vtype.name), FuncOutput(lambda: getVar("_"+c)))
	def run(self, args):
		pushStackFrame()
		for (c, _, _), a in zip(self.params, args):
			putVar("_"+c, a)
		for cmd in self.body:
			cmd[0]()
			if "stop action" in SCOPE[-1].bits:
				break
		popStackFrame()

# jälkimmäinen sarake kertoo, syrjäytyvätkö tämäntyyppiset säännöt, jos toiseksi jälkimmäisessä sarakkeessa vastaava syrjäyttävä sääntö täsmää

LISTENER_PRIORITIES = [
#	 PRE       CASE     POST       PRI SPECIAL GENERAL
	("ennen", "osanto", "",        20, False,  False),
	("",      "omanto", "sijasta", 40, True,   False),
	("",      "omanto", "aikana",  50, False,  True),
	("",      "omanto", "jälkeen", 80, False,  False),
]

ACTION_LISTENERS = []

def defineAction(name, params, pre, post):
	action = RAction(name)
	
	def defineActionListener(patterns, priority, is_special_case, is_general_case):
		listener = RListener(action, [(a_case, pattern, name) for (pattern, name), (_, _, a_case) in zip(patterns, params)], priority, is_special_case, is_general_case)
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
	
	def addListenerDefPattern(p_pre, p_case, p_post, priority, is_special_case, is_general_case, nameds):
		pgl(".LISTENER-DEF-%d ::= %s %s %s %s{-minen,%s} %s %s : -> def %s($1):" % (
			action.id,
			p_pre,
			" ".join([
				"%s .PATTERN-%d{%s,yksikkö}" % (tokensToCode(a_pre), a_class.id, a_case)
				+ (" ( .* )" if named else "")
			for named, (a_pre, a_class, a_case) in zip(nameds, params)]),
			tokensToCode(pre), name.baseform("-minen"), p_case, tokensToCode(post), p_post,
			name.token
		), FuncOutput(lambda *groups: defineActionListener(separateGroups(groups, nameds), priority, is_special_case, is_general_case)))
	
	for p_pre, p_case, p_post, priority, is_special_case, is_general_case in LISTENER_PRIORITIES:
		for nameds in itertools.product(*[[False, True]]*len(params)):
			addListenerDefPattern(p_pre, p_case, p_post, priority, is_special_case, is_general_case, nameds)
	pgl(".DEF ::= .LISTENER-DEF-%d -> $1" % (action.id,), identity)
	
	def defineCommand(category, cmd_cases, pre, *posts):
		pgl(".%s ::= %s %s . -> %s($1)" % (
			category,
			tokensToCode(pre),
			" ".join([
				".EXPR-%d{%s,yksikkö} %s" % (a_class.id, cmd_case, tokensToCode(post))
			for cmd_case, (_, a_class, _), post in zip(cmd_cases, params, posts)]),
			name.token
		), FuncOutput(lambda *val: action.run(val)))
	
	def addCommandDefPhrase(cmd_cases):
		cmd_pattern = " ".join([
				"[ " + a_class.nameToCode({cmd_case, "yksikkö"}) + " ] .**"
			for cmd_case, (_, a_class, _) in zip(cmd_cases, params)])
		action_patterns = [
			"%s %s{-minen,CASE} %s" % (
				tokensToCode(pre), name.baseform("-minen"), tokensToCode(post),
			)
		]
		if len(params) != 0:
			action_patterns.append(
				"%s %s %s{-minen,CASE} %s" % (
					" ".join([
						tokensToCode(a_pre) + a_class.nameToCode({a_case, "yksikkö"})
					for a_pre, a_class, a_case in params]),
					tokensToCode(pre), name.baseform("-minen"), tokensToCode(post)
				)
			)
			if sum([len(a_pre) for a_pre, _, _ in params]) + len(pre) + len(post) != 0:
				action_patterns.append(
					"%s %s %s{-minen,CASE} %s" % (
						" ".join([tokensToCode(a_pre) for a_pre, _, _ in params]),
						tokensToCode(pre), name.baseform("-minen"), tokensToCode(post),
					)
				)
		for action_pattern in action_patterns:
			pgl(".COMMAND-DEF-%d ::= %s komento on \" .** %s \" . -> def %s command" % (
				action.id,
				action_pattern.replace("CASE", "omanto"),
				cmd_pattern,
				name.token
			), FuncOutput(lambda *p: defineCommand("CMD", cmd_cases, *p)))
			pgl(".COMMAND-DEF-%d ::= tulkitse \" .** %s \" %s . -> def %s command" % (
				action.id,
				cmd_pattern,
				action_pattern.replace("CASE", "olento"),
				name.token
			), FuncOutput(lambda *p: defineCommand("PLAYER-CMD", cmd_cases, *p)))
	
	for cmd_cases in itertools.product(*[CASES]*len(params)):
		addCommandDefPhrase(cmd_cases)
	
	pgl(".DEF ::= .COMMAND-DEF-%d -> $1" % (action.id,), identity)

def addActionDefPattern(cases):
	def transformArgs(args):
		ans = []
		i = -2
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

# Sisäänrakennetut luokat

asia = defineClass(tokenize("asia"), None)

ei_mikään = asia.newInstance()
pgl(".EXPR-%d ::= ei-mikään{$} -> ei-mikään" % (asia.id,), FuncOutput(lambda: ei_mikään))

def createStringObj(x):
	return merkkijono.newInstance().setExtra("str", x)

merkkijono = defineClass(tokenize("merkkijono"), asia)
pgl('.EXPR-%d ::= " .STR-CONTENT " -> "$1"' % (asia.id,), FuncOutput(createStringObj))
pgl('.EXPR-%d ::= " .STR-CONTENT " -> "$1"' % (merkkijono.id,), FuncOutput(createStringObj))
newline_obj = createStringObj("\n")
pgl('.EXPR-%d ::= rivinvaihto{$} -> "\\n"' % (merkkijono.id,), FuncOutput(lambda: newline_obj))
pgl('.EXPR-%d ::= .EXPR-%d{$} isolla alkukirjaimella -> capitalize($1)' % (merkkijono.id, merkkijono.id), FuncOutput(lambda x: createStringObj(x.extra["str"].capitalize())))

# Tulostaminen

def printCommand(value):
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
			sys.stderr.write("Virhe jäsennettäessä riviä `" + line.strip() + "'. Vaihtoehdot: " + ", ".join([a[1] for a in alternatives]) + "\n")
			break
		ans.append(alternatives[0])
	return ans

# Tiedoston lataaminen

def loadFile(file):
	with open(file, "r") as f:
		while True:
			l = f.readline()
			if not l:
				break
			if not l.strip() or l[0] == ">":
				continue
			a = GRAMMAR.matchAll(tokenize(l.strip()), "DEF", set())
			if len(a) == 1:
				t = a[0][0]()
				if a[0][1][-1] == ":":
					t.parse(f)
			else:
				print("Virhe jäsennettäessä tiedoston riviä `" + l.strip() + "'.")
# Standardikirjasto

my_path = os.path.dirname(os.path.realpath(__file__))
loadFile(os.path.join(my_path, "std.txt"))

# Pääohjelma

def main():
	def complete_file(t, s):
		path, file = os.path.split(t)
		alternatives = []
		try:
			for c in sorted(["/kielioppi", "/käsitteet", "/debug ", "/virheet", "/match ", "/eval ", "/lataa ", "/pelitila", "/komentotila", "/määrittelytila"]):
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
	
	def printStatistics():
		n_patterns = sum([len(category) for category in GRAMMAR.patterns.values()])
		print("Ladattu", n_patterns, "fraasia.")
	
	mode = ["DEF", "CMD", "PLAYER-CMD"]
	mode_chars = ["!", "?"]
	
	printStatistics()
	while True:
		try:
			line = input(">> ")
		except EOFError:
			break
		if not line:
			continue
		if line == "/kielioppi":
			GRAMMAR.print()
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
			ints = GRAMMAR.matchAll(tokenize(expr), cat, set())
			for _, string in ints:
				print(string)
			continue
		elif line.startswith("/eval"):
			print(eval(line[5:].strip()))
			continue
		elif line.startswith("/lataa"):
			loadFile(line[6:].strip())
			printStatistics()
			continue
		elif line.startswith("/pelitila"):
			mode = ["PLAYER-CMD", "CMD", "DEF"]
			continue
		elif line.startswith("/komentotila"):
			mode = ["CMD", "DEF", "PLAYER-CMD"]
			continue
		elif line.startswith("/määrittelytila"):
			mode = ["DEF", "CMD", "PLAYER-CMD"]
			continue
		del ERRORS[:]
		phrase_type = mode[0]
		if line[0] in mode_chars:
			phrase_type = mode[mode_chars.index(line[0])+1]
			line = line[1:]
		interpretations = GRAMMAR.matchAll(tokenize(line), phrase_type, set())
		if len(interpretations) == 0:
			print("Ei tulkintaa.")
		elif len(interpretations) == 1:
			if not mode[0] == phrase_type == "PLAYER-CMD":
				print(interpretations[0][1])
			interpretations[0][0]()
		else:
			print("Löydetty", len(interpretations), "tulkintaa:")
			for _, interpretation in interpretations:
				print(interpretation)
		if not mode[0] == phrase_type == "PLAYER-CMD":
			printStatistics()
			

if __name__ == "__main__":
	main()
