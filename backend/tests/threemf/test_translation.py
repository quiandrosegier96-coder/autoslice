from app.threemf.domain.diagnostics import Severity, TranslationItem, TranslationReport, TranslationStatus


def test_weighted_score_penalizes_high_impact_loss_more():
    low = TranslationReport((TranslationItem("comment", TranslationStatus.UNSUPPORTED, Severity.LOW),)).with_weighted_score()
    high = TranslationReport((TranslationItem("placement", TranslationStatus.UNSUPPORTED, Severity.HIGH),)).with_weighted_score()
    assert high.compatibility_score < low.compatibility_score


def test_preserved_feature_has_no_penalty():
    report = TranslationReport((TranslationItem("materials", TranslationStatus.PRESERVED, Severity.HIGH),)).with_weighted_score()
    assert report.compatibility_score == 100.0


def test_weighted_scores_order_no_low_medium_high_loss():
    score = lambda severity: TranslationReport((
        TranslationItem("feature", TranslationStatus.UNSUPPORTED, severity),
    )).with_weighted_score().compatibility_score
    assert 100.0 > score(Severity.LOW) > score(Severity.MEDIUM) > score(Severity.HIGH)
