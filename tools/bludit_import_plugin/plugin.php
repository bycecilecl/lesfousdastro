<?php defined('BLUDIT') or die('Bludit CMS.');

class pluginFousBlogImport extends Plugin
{
    private const CATEGORIES = [
        'bases' => 'Les Bases',
        'signe' => 'Signes astrologiques',
        'planete' => 'Planètes',
        'maison' => 'Maisons',
        'analyses' => 'Analyses de thèmes',
        'astropapote' => 'Astropapote',
        'carnets' => "Carnets d'astrologue",
        'vedique' => 'Astrologie védique',
        'uranienne' => 'Astrologie uranienne',
    ];

    private function articles(): array
    {
        $articles = require __DIR__ . '/articles.php';
        if (!is_array($articles) || count($articles) !== 42) {
            throw new RuntimeException('Le lot de 42 articles est incomplet.');
        }
        return $articles;
    }

    private function categoryKey(string $name, string $wantedKey): string
    {
        global $categories;
        foreach ($categories->getDB() as $key => $row) {
            if (($row['name'] ?? '') === $name) {
                return (string) $key;
            }
        }
        if (isset($categories->getDB()[$wantedKey])) {
            throw new RuntimeException('La catégorie ' . $wantedKey . ' existe déjà avec un autre nom.');
        }
        $generatedKey = (string) $categories->add(['name' => $name, 'description' => '']);
        if ($generatedKey !== $wantedKey) {
            if (!$categories->edit([
                'name' => $name,
                'oldKey' => $generatedKey,
                'newKey' => $wantedKey,
                'description' => '',
            ])) {
                throw new RuntimeException('Impossible de créer la catégorie ' . $name . '.');
            }
        }
        return $wantedKey;
    }

    public function adminSidebar(): string
    {
        if (!checkRole(['admin'], false)) { return ''; }
        return '<a class="nav-link" href="' . HTML_PATH_ADMIN_ROOT . 'plugin/pluginFousBlogImport">Importer les anciens articles</a>';
    }

    public function adminController(): void
    {
        global $layout, $pages;
        checkRole(['admin']);
        header('Cache-Control: private, no-store, max-age=0');
        header('X-Robots-Tag: noindex, nofollow');
        $layout['title'] = 'Importer les anciens articles — ' . $layout['title'];
        if ($_SERVER['REQUEST_METHOD'] !== 'POST') { return; }

        try {
            if (($_POST['fous_import_action'] ?? '') !== 'drafts') {
                throw new RuntimeException('Action inconnue.');
            }
            $created = 0;
            $skipped = 0;
            foreach ($this->articles() as $article) {
                $slug = (string) ($article['slug'] ?? '');
                if (!preg_match('/^[a-z0-9]+(?:-[a-z0-9]+)*$/D', $slug)) {
                    throw new RuntimeException('Adresse d’article invalide.');
                }
                if ($pages->exists($slug)) {
                    $skipped++;
                    continue;
                }
                $wantedKey = (string) ($article['category'] ?? '');
                $label = self::CATEGORIES[$wantedKey] ?? '';
                if ($label === '') {
                    throw new RuntimeException('Catégorie inconnue pour ' . $slug);
                }
                $article['category'] = $this->categoryKey($label, $wantedKey);
                // The import must never publish an article, including on retry.
                $article['type'] = 'draft';
                if (createPage($article) === false) {
                    throw new RuntimeException('Import interrompu sur ' . $slug . '. Relance-le pour reprendre.');
                }
                $created++;
            }
            Session::set('fous_import_notice', ['ok' => true, 'text' => $created . ' brouillons créés ; ' . $skipped . ' articles déjà présents conservés.']);
        } catch (Throwable $error) {
            Session::set('fous_import_notice', ['ok' => false, 'text' => $error->getMessage()]);
        }
        header('Location: ' . HTML_PATH_ADMIN_ROOT . 'plugin/pluginFousBlogImport', true, 303);
        exit;
    }

    public function adminView(): string
    {
        global $pages, $security;
        checkRole(['admin']);
        $articles = $this->articles();
        $remaining = 0;
        foreach ($articles as $article) {
            if (!$pages->exists((string) $article['slug'])) { $remaining++; }
        }
        $notice = Session::get('fous_import_notice');
        Session::remove('fous_import_notice');
        $csrf = htmlspecialchars($security->getTokenCSRF(), ENT_QUOTES, 'UTF-8');
        $target = htmlspecialchars(HTML_PATH_ADMIN_ROOT . 'plugin/pluginFousBlogImport', ENT_QUOTES, 'UTF-8');
        ob_start(); ?>
        <div class="container-fluid pb-5">
          <h1>Rapatrier le blog des Fous d’Astro</h1>
          <p>Les 42 articles seront copiés comme <strong>brouillons</strong>, avec leur titre, leur adresse, leur description, leur date, leur catégorie et leur contenu. Les articles déjà présents dans Bludit seront conservés.</p>
          <p><strong><?= $remaining ?> article(s) à importer.</strong> Tu pourras ensuite les ouvrir et les retravailler un par un.</p>
          <div class="alert alert-warning" role="note">La date de « Dominance des éléments dans le thème astral » est mal saisie dans l’ancien blog. Le brouillon portera provisoirement la date du 15 juin 2022. Vérifie-la avant de publier cet article.</div>
          <?php if (is_array($notice)): ?><div class="alert <?= !empty($notice['ok']) ? 'alert-success' : 'alert-danger' ?>" role="alert"><?= htmlspecialchars((string) ($notice['text'] ?? ''), ENT_QUOTES, 'UTF-8') ?></div><?php endif; ?>
          <?php if ($remaining): ?><form method="post" action="<?= $target ?>">
            <input type="hidden" name="tokenCSRF" value="<?= $csrf ?>">
            <input type="hidden" name="fous_import_action" value="drafts">
            <button class="btn btn-primary" type="submit">Importer les brouillons</button>
          </form><?php endif; ?>
        </div>
        <?php return (string) ob_get_clean();
    }
}
