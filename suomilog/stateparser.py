#"Tulosta" [
#	teksti<-$nimi:nimento
#]
#
#ihminen :: OLENTO
#
#OLENTO:omanto [
#	omistaja->$nimi:*
#	omistaja->$pituus:*
#	omistaja->@lapset:*
#	omistaja->LAPSI:*
#]
#
#$nimi:* [
#	koko<-KIRJAINKOKO:ulko-olento
#	.
#]
#
#KIRJAINKOKO:x {
#	@'iso:x [
#		koko->@kirjain:x
#	]
#	@'pieni:x [
#		koko->@kirjain:x
#	]
#}
#
#lapsi :: OLENTO
#
#LAPSI:x {
#	$ensimmäinen:x [
#		mones->$lapsi:x
#	]
#	$toinen:x [
#		mones->$lapsi:x
#	]
#}

#PYTHONILLA:

class TokenList:
	def __init__(self, tokens):
		self.tokens = tokens
	def __getitem__(self, i):
		return self.tokens[i]
	def __len__(self):
		return len(self.tokens)

class Word:
	def __init__(self, token, baseform, form, number, relations={}):
		self.token = token
		self.baseform = baseform
		self.form = form
		self.number = number
		self.relations = relations
	def update(self, relation, word):
		return Word(self.token, self.baseform, self.form, self.number, {**self.relations, relation: word})
	def __repr__(self):
		return self.baseform + ":" + self.form + ":" + self.number + repr(self.relations)

class Alternative:
	def __init__(self, pattern, relation, dominative):
		self.pattern = pattern
		self.relation = relation
		self.dominative = dominative
	def __repr__(self):
		return self.relation + ("->" if self.dominative else "<-") + repr(self.pattern)

class Namespace:
	def __init__(self, rules, parameters):
		self._rules = rules
		self._parameters = parameters
	def rules(self):
		return self._rules
	def parameters(self):
		return self._parameters

class NamespaceReference:
	def __init__(self, name):
		self.ref_name = name
	def rules(self):
		return NAMESPACES[self.ref_name]._rules
	def parameters(self):
		return NAMESPACES[self.ref_name]._parameters
	def __repr__(self):
		return self.ref_name

class Pattern:
	def __init__(self, baseform, form, number):
		self.baseform = baseform
		self.form = form
		self.number = number
	def isSubnamespacePattern(self):
		return isinstance(self.baseform, NamespaceReference) or isinstance(self.baseform, Namespace)
	def match(self, word):
		if ((isinstance(self.baseform, str) and self.baseform == word.baseform or word.baseform in self.baseform)
			and (len(self.form) <= 1 or self.form == word.form)
			and (len(self.number) <= 1 or self.number == word.number)):
			subs = {}
			if len(self.form) == 1:
				subs[self.form] = word.form
			if len(self.number) == 1:
				subs[self.number] = word.number
			return subs
		else:
			return None
	def subs(self, subs):
		return Pattern(
			self.baseform,
			self.form if len(self.form) > 1 else subs.get(self.form, self.form),
			self.number if len(self.number) > 1 else subs.get(self.number, self.number))
	def __repr__(self):
		return repr(self.baseform) + ":" + self.form + ":" + self.number

class LiteralPattern:
	def __init__(self, baseform):
		self.baseform = baseform
	def isSubnamespacePattern(self):
		return False
	def match(self, word):
		return {} if word.token == self.baseform else None
	def subs(self, subs):
		return self

class Environment:
	def __init__(self, rules, tokens, place=0, current_object=None, substitutions={}, onEnd=lambda env: []):
		if current_object is None:
			current_object = tokens[place]
			place += 1
		self.rules = rules
		self.tokens = tokens
		self.place = place
		self.current_object = current_object
		self.substitutions = substitutions
		self.onEnd = onEnd
	def hasNext(self):
		return len(self.tokens) > self.place
	def nextWord(self):
		return self.tokens[self.place]
	def next(self, word, alt, altpattern):
		def update(env, next_word, delta):
			if alt.dominative:
				new_obj = next_word.update(alt.relation, self.current_object)
			else:
				new_obj = self.current_object.update(alt.relation, next_word)
			return Environment(self.rules, self.tokens, env.place+delta, new_obj, substitutions=self.substitutions, onEnd=self.onEnd)
		if altpattern.isSubnamespacePattern():
			form_var, number_var = altpattern.baseform.parameters()
			subs = {form_var: altpattern.form, number_var: altpattern.number}
			return Environment(alt.pattern.baseform.rules(), self.tokens, self.place, substitutions=subs, onEnd=lambda env: [update(env, env.current_object, 0)])
		else:
			return update(self, word, 1)

class Rule:
	def __init__(self, pattern, alternatives, can_end):
		self.pattern = pattern
		self.alternatives = alternatives
		self.can_end = can_end
	def match(self, env):
		pattern = self.pattern.subs(env.substitutions)
		subs = pattern.match(env.current_object)
		#print(subs, env.place)
		if subs is not None:
			ans = env.onEnd(env) if self.can_end else []
			if env.hasNext():
				word = env.nextWord()
				for alt in self.alternatives:
					altpattern = alt.pattern.subs(subs).subs(env.substitutions)
					#print(word, altpattern)
					if altpattern.isSubnamespacePattern() or altpattern.match(word) is not None:
						ans.append(env.next(word, alt, altpattern))
			return True, ans
			
		else:
			return False, []
	def __repr__(self):
		return repr(self.pattern) + " [" + ",".join(map(repr, self.alternatives)) + "]"

def parse(rules, tokens):
	ans = []
	def onEnd(env):
		nonlocal ans
		if not env.hasNext():
			ans.append(env.current_object)
		return []
	envs = [Environment(rules, tokens, onEnd=onEnd)]
	while envs:
		new_envs = []
		for env in envs:
			found = False
			for rule in env.rules:
				print(env.current_object, rule)
				matches, news = rule.match(env)
				print("->", news)
				if matches:
					new_envs += news
					found = True
			if not found:
				new_envs += env.onEnd(env)
		envs = new_envs
	return ans

def main():
	global NAMESPACES
	NAMESPACES = {}
	NAMESPACES["LAPSI"] = Namespace([
		Rule(Pattern("ensimmäinen", "f", "x"), [Alternative(Pattern("lapsi", "f", "x"), "mones", True)], False),
		Rule(Pattern("toinen", "f", "x"), [Alternative(Pattern("lapsi", "f", "x"), "mones", True)], False)
	], ("f", "n"))
	NAMESPACES["KIRJAINKOKO"] = Namespace([
		Rule(Pattern("iso", "f", "monikko"), [Alternative(Pattern("kirjain", "f", "monikko"), "koko", True)], False),
		Rule(Pattern("pieni", "f", "monikko"), [Alternative(Pattern("kirjain", "f", "monikko"), "koko", True)], False)
	], ("f", "n"))
	olento = ["pelaaja", "lapsi"]
	merkkijono = ["nimi"]
	rules = [
		Rule(Pattern(olento, "omanto", "yksikkö"), [
			Alternative(Pattern(NamespaceReference("LAPSI"), "", ""), "omistaja", True),
			Alternative(Pattern("nimi", "", "yksikkö"), "omistaja", True)
		], False),
		Rule(Pattern(merkkijono, "", "yksikkö"), [
			Alternative(Pattern(NamespaceReference("KIRJAINKOKO"), "ulkoolento", ""), "tyyli", False)
		], True)
	]
	tokens = TokenList([
		Word("pelaajan", "pelaaja", "omanto", "yksikkö"),
		Word("toisen", "toinen", "omanto", "yksikkö"),
		Word("lapsen", "lapsi", "omanto", "yksikkö"),
		Word("nimi", "nimi", "nimento", "yksikkö"),
		Word("pienillä", "pieni", "ulkoolento", "monikko"),
		Word("kirjaimilla", "kirjain", "ulkoolento", "monikko")
	])
	print("ans", parse(rules, tokens))

main()
