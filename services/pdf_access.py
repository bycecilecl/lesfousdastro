"""Only explicitly published examples may be served by legacy PDF URLs."""
from flask import abort, request

PUBLIC_PDF_EXAMPLES = frozenset({
    'Flash_Transits_Britney_Spears_2008-02-01_2026-09-04_16-13-44.pdf',
    'Exemple_Point_Astral_Cecile.pdf', 'Point_Astral_Britney_Spears.pdf',
    'Exemple_Profil_Amoureux.pdf', 'Exemple_Flash_Astral_Cecile.pdf',
    'Exemple_Point_Astral_Cecile_SVG.pdf', 'Exemple_Forces_Defis.pdf',
    'Analyse_Karmique_Britney_2026-04-30_15-42.pdf', 'Forces_Defis_exemple.pdf',
})
LEGACY_PDF_ENDPOINTS = frozenset({
    'point_astral_blocs.telecharger_point_astral',
    'point_astral_famille.telecharger_point_astral',
    'analyse_karmique.telecharger_analyse_karmique',
    'profil_amoureux_module.telecharger_profil_amoureux_pdf',
    'amour_blocs.telecharger_amour_pdf',
})


def install_pdf_access(app):
    @app.before_request
    def restrict_public_reports():
        args = request.view_args or {}
        if request.endpoint == 'static':
            filename = args.get('filename', '')
            if filename.startswith('pdfs/') and filename[5:] not in PUBLIC_PDF_EXAMPLES:
                abort(404)
            if filename.startswith('html/'):
                abort(404)
        if request.endpoint in LEGACY_PDF_ENDPOINTS:
            if args.get('nom_fichier', '') + '.pdf' not in PUBLIC_PDF_EXAMPLES:
                abort(404)
        if request.endpoint in {'point_astral_blocs.apercu_point_astral',
                                'point_astral_famille.apercu_point_astral'}:
            abort(404)
