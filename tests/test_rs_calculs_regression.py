"""Régressions factuelles RS, sans appels IA, email ou réseau."""
import contextlib
import io
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import pytz
import swisseph as swe
from utils.revolution_solaire.calculs_astrologiques_rs import detecter_interceptions
from utils.revolution_solaire.calcul_theme_rs import calcul_theme
from utils.revolution_solaire.calcul_retour_solaire import trouver_retour_solaire
from utils.revolution_solaire.theme_revolution_solaire import calculer_theme_revolution_solaire, _instant_naissance_utc
from utils.revolution_solaire.donnees_techniques import extraire_donnees_revolution_solaire
from utils.revolution_solaire.rapport_technique import generer_rapport_technique


class RetoursSolairesTest(unittest.TestCase):
    def test_fin_decembre_bonne_annee(self):
        for jour in [24,25,26,30,31]:
            with self.subTest(jour=jour):
                r=trouver_retour_solaire(datetime(1980,12,jour,12,tzinfo=timezone.utc),2026)
                self.assertEqual(r['retour_utc'].year,2026)
                self.assertLess(r['ecart_degres'],1e-6)

    def test_cycles_consecutifs_y_compris_premier_janvier(self):
        for mois,jour in [(1,1),(12,31),(2,29)]:
            with self.subTest(mois=mois,jour=jour):
                naissance=datetime(1980,mois,jour,12,tzinfo=timezone.utc)
                debut=trouver_retour_solaire(naissance,2026)['retour_utc']
                fin=trouver_retour_solaire(naissance,2027)['retour_utc']
                self.assertTrue(364 < (fin-debut).total_seconds()/86400 < 367)
                self.assertLess(abs((debut-datetime(2026,mois,min(jour,28),12,tzinfo=timezone.utc)).days),5)

    def test_civil_et_utc_sur_deux_annees(self):
        for date,heure,tzid in [('2000-01-01','00:30','Pacific/Kiritimati'),('2000-12-31','23:30','Pacific/Honolulu')]:
            with self.subTest(tzid=tzid):
                birth={'date':date,'heure':heure,'lieu':'Test','lat':0,'lon':0,'tzid':tzid}
                lieu={'lieu':'Test','lat':0,'lon':0,'tzid':tzid}
                with patch('utils.revolution_solaire.theme_revolution_solaire.calcul_theme',return_value={}):
                    c=calculer_theme_revolution_solaire('Test',birth,lieu,2026)
                self.assertEqual(c['age_au_retour'],26)
                expected=_instant_naissance_utc(birth).timestamp()+26*365.2422*86400
                self.assertLess(abs(c['retour']['retour_utc'].timestamp()-expected),3*86400)
                self.assertEqual(c['annee_rs'],2026)
                self.assertEqual(c['naissance_locale'].year,2000)

    def test_heure_ambigue_refusee(self):
        with self.assertRaises(ValueError):
            _instant_naissance_utc({'date':'2025-10-26','heure':'02:30','tzid':'Europe/Paris'})

    def test_heure_inexistante_refusee(self):
        with self.assertRaises(ValueError):
            _instant_naissance_utc({'date':'2025-03-30','heure':'02:30','tzid':'Europe/Paris'})

    def test_annee_invalide(self):
        for annee in [True,1980,'2026']:
            with self.subTest(annee=annee),self.assertRaises(ValueError):
                trouver_retour_solaire(datetime(1980,1,1,tzinfo=timezone.utc),annee)


class InterceptionsTest(unittest.TestCase):
    def test_belier_et_quatre_signes(self):
        cusps,_=swe.houses(swe.julday(2026,1,1,7),48.8566,2.35,b'P')
        r=detecter_interceptions(cusps)
        self.assertEqual(r['maisons_interceptées'],{'Bélier':'Maison 3','Cancer':'Maison 7','Balance':'Maison 9','Capricorne':'Maison 1'})
        self.assertEqual(r['axes_interceptes'],[('Bélier','Balance'),('Cancer','Capricorne')])

    def test_sans_interception_et_cuspides_exactes(self):
        for offset in [0,0.001,29.999]:
            with self.subTest(offset=offset):
                r=detecter_interceptions([(offset+30*i)%360 for i in range(12)])
                self.assertEqual(r,{'signes_interceptes':[],'axes_interceptes':[],'maisons_interceptées':{}})

    def test_cuspides_invalides(self):
        for cuspides in [[],[float('nan')]*12,[float('inf')]*12]:
            with self.assertRaises(ValueError):detecter_interceptions(cuspides)


class DonneesRS2014Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.birth={'date':'1980-10-11','heure':'06:38','lieu':'Chalon-sur-Saône','lat':46.7805555556,'lon':4.8527777778,'tzid':'Europe/Paris'}
        cls.lieu={'lieu':'Paris','lat':48.8566,'lon':2.3522,'tzid':'Europe/Paris'}
        with contextlib.redirect_stdout(io.StringIO()):
            cls.c=calculer_theme_revolution_solaire('Test',cls.birth,cls.lieu,2014)
            cls.d=extraire_donnees_revolution_solaire(cls.c['theme_natal'],cls.c['theme_revolution_solaire'],age_profection=34)

    def test_date_reference_preservee(self):
        attendu=datetime(2014,10,11,11,11,32,tzinfo=timezone.utc)
        self.assertLess(abs((self.c['retour']['retour_utc']-attendu).total_seconds()),1)
        self.assertEqual(self.c['age_au_retour'],34)

    def test_retrogradations_depuis_ephemerides(self):
        dt=self.c['retour']['retour_utc']
        jd=swe.julday(dt.year,dt.month,dt.day,dt.hour+dt.minute/60+dt.second/3600)
        for nom,code in [('Mercure',swe.MERCURY),('Vénus',swe.VENUS),('Mars',swe.MARS),('Jupiter',swe.JUPITER),('Saturne',swe.SATURN),('Uranus',swe.URANUS),('Neptune',swe.NEPTUNE),('Pluton',swe.PLUTO)]:
            with self.subTest(nom=nom):
                self.assertEqual(self.d['placements_rs'][nom]['retrograde'],swe.calc_ut(jd,code)[0][3]<0)
        self.assertTrue(self.d['placements_rs']['Uranus']['retrograde'])
        self.assertTrue(self.d['placements_rs']['Neptune']['retrograde'])
        self.assertFalse(self.d['placements_rs']['Pluton']['retrograde'])

    def test_pluton_retrograde_autre_date(self):
        with contextlib.redirect_stdout(io.StringIO()):
            t=calcul_theme('Test','2026-06-01','12:00','Paris',lat=48.8566,lon=2.3522,dt_naissance_utc=datetime(2026,6,1,12,tzinfo=timezone.utc),tzid='UTC')
        self.assertLess(swe.calc_ut(swe.julday(2026,6,1,12),swe.PLUTO)[0][3],0)
        self.assertTrue(t['planetes']['Pluton']['retrograde'])

    def test_retrogradations_dans_source_claude(self):
        texte=generer_rapport_technique(self.d,self.c['retour_local'])
        for nom in ['Mercure','Uranus','Neptune']:
            self.assertTrue(any(l.startswith('- '+nom+' RS :') and 'rétrograde' in l for l in texte.splitlines()),nom)
        self.assertFalse(any(l.startswith('- Pluton RS :') and 'rétrograde' in l for l in texte.splitlines()))

    def test_natal_et_superposition_distincts(self):
        self.assertEqual(self.d['placements_natals_verifies']['Rahu']['maison'],10)
        self.assertEqual(self.d['placements_rs']['Rahu']['maison_natale'],1)
        self.assertEqual(self.d['placements_natals_verifies']['Vénus']['maison'],11)
        self.assertEqual(self.d['placements_rs']['Vénus']['maison_natale'],1)

    def test_interceptions_reference(self):
        self.assertEqual(self.d['interceptions_rs']['maisons_interceptées'],{'Verseau':'Maison 2','Lion':'Maison 8'})


if __name__=='__main__':unittest.main()
