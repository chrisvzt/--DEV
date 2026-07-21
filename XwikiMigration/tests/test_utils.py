from cil_migrate.downloader import safe_name


def test_safe_name_replaces_windows_characters():
    assert safe_name('A:B/C*D?.pdf') == 'A_B_C_D_.pdf'
