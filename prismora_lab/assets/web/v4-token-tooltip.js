(() => {
  'use strict';

  const translations = {
    fr: {
      '中国':'Chine','首都':'capitale','北京':'Pékin','中华人民共和国':'République populaire de Chine','人民':'peuple','共和国':'république','大陆':'Chine continentale','简体':'écriture simplifiée','台湾':'Taïwan','北京城':'ville de Pékin','の':'de / particule possessive','です':'est / forme polie','ペキン':'Pékin','中国語':'langue chinoise','日本':'Japon','日本語':'japonais','首都圏':'région capitale','china':'Chine','chinese':'chinois / chinoise','beijing':'Pékin','capital':'capitale','mainland':'continent / Chine continentale','simplified':'simplifié','writing':'écriture','people':'peuple','republic':'république','same':'identique / même','path':'chemin','demo':'démonstration','answer':'réponse','token':'jeton','layer':'couche','many':'beaucoup','countries':'pays','american':'américain','european':'européen','universities':'universités','japanese':'japonais','glavni grad':'capitale','glavni':'principal','grad':'ville','kina':'Chine','peking':'Pékin','beograd':'Belgrade','država':'État / pays','republika':'république','narod':'peuple','je':'est','nije':'n’est pas','da':'oui / que','ne':'non / ne…pas','u':'dans','i':'et','od':'de / depuis','za':'pour'
    },
    en: {
      '中国':'China','首都':'capital','北京':'Beijing','中华人民共和国':'People’s Republic of China','人民':'people','共和国':'republic','大陆':'mainland China','简体':'simplified script','台湾':'Taiwan','北京城':'city of Beijing','の':'of / possessive particle','です':'is / polite copula','ペキン':'Beijing','中国語':'Chinese language','日本':'Japan','日本語':'Japanese','首都圏':'capital region','chine':'China','chinois':'Chinese','chinoise':'Chinese','pékin':'Beijing','capitale':'capital','continent':'mainland','peuple':'people','république':'republic','identique':'same','même':'same','chemin':'path','démonstration':'demo','réponse':'answer','jeton':'token','couche':'layer','beaucoup':'many','pays':'country / countries','américain':'American','européen':'European','universités':'universities','japonais':'Japanese','glavni grad':'capital','glavni':'main / principal','grad':'city','kina':'China','peking':'Beijing','beograd':'Belgrade','država':'state / country','republika':'republic','narod':'people','je':'is','nije':'is not','da':'yes / that','ne':'no / not','u':'in','i':'and','od':'from / of','za':'for'
    }
  };

  const copy = {
    fr: { unavailable:'Traduction locale non disponible', han:'caractères han', kana:'kana japonais', cyrillic:'alphabet cyrillique', latin:'alphabet latin', mixed:'écriture mixte' },
    en: { unavailable:'No local translation available', han:'Han characters', kana:'Japanese kana', cyrillic:'Cyrillic script', latin:'Latin script', mixed:'mixed script' },
  };

  const tooltip = document.createElement('div');
  tooltip.className = 'token-tooltip';
  tooltip.setAttribute('role', 'tooltip');
  tooltip.innerHTML = '<span class="token-original"></span><span class="token-translation"></span><span class="token-meta"></span>';
  document.body.append(tooltip);

  const normalize = (value) => String(value || '')
    .replace(/\*\*/g, '')
    .replace(/^[\s"“”'‘’.,;:!?()[\]{}]+|[\s"“”'‘’.,;:!?()[\]{}]+$/g, '')
    .trim();

  function scriptOf(value) {
    const hasHan = /\p{Script=Han}/u.test(value);
    const hasKana = /[\p{Script=Hiragana}\p{Script=Katakana}]/u.test(value);
    const hasCyrillic = /\p{Script=Cyrillic}/u.test(value);
    const hasLatin = /\p{Script=Latin}/u.test(value);
    const count = [hasHan, hasKana, hasCyrillic, hasLatin].filter(Boolean).length;
    if (count > 1) return 'mixed';
    if (hasHan) return 'han';
    if (hasKana) return 'kana';
    if (hasCyrillic) return 'cyrillic';
    if (hasLatin) return 'latin';
    return 'mixed';
  }

  function translationFor(value, lang) {
    const cleaned = normalize(value);
    if (!cleaned) return null;
    const dictionary = translations[lang] || translations.en;
    return dictionary[cleaned] || dictionary[cleaned.toLowerCase()] || null;
  }

  function position(event) {
    const margin = 14;
    const width = tooltip.offsetWidth || 260;
    const height = tooltip.offsetHeight || 80;
    let left = event.clientX + 16;
    let top = event.clientY + 16;
    if (left + width + margin > innerWidth) left = event.clientX - width - 16;
    if (top + height + margin > innerHeight) top = event.clientY - height - 16;
    tooltip.style.left = `${Math.max(margin, left)}px`;
    tooltip.style.top = `${Math.max(margin, top)}px`;
  }

  function tokenTarget(node) {
    return node?.closest?.('.token, .candidate strong');
  }

  document.addEventListener('pointerover', (event) => {
    const target = tokenTarget(event.target);
    if (!target) return;
    const original = normalize(target.textContent);
    if (!original || /^[\p{P}\p{S}]+$/u.test(original)) return;
    const lang = document.documentElement.lang === 'fr' ? 'fr' : 'en';
    const translated = translationFor(original, lang);
    tooltip.querySelector('.token-original').textContent = original;
    tooltip.querySelector('.token-translation').textContent = translated || copy[lang].unavailable;
    tooltip.querySelector('.token-meta').textContent = copy[lang][scriptOf(original)];
    tooltip.classList.add('visible');
    position(event);
  });

  document.addEventListener('pointermove', (event) => {
    if (tooltip.classList.contains('visible')) position(event);
  });

  document.addEventListener('pointerout', (event) => {
    const target = tokenTarget(event.target);
    if (!target) return;
    const related = tokenTarget(event.relatedTarget);
    if (related === target) return;
    tooltip.classList.remove('visible');
  });
})();
