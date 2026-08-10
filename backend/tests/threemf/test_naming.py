from app.threemf.pipeline.naming import autoslice_output_filename


def test_autoslice_output_name():
    assert autoslice_output_filename("dragon.3mf") == "dragon_AutoSlice.3mf"


def test_autoslice_output_name_avoids_existing_suffix():
    assert autoslice_output_filename("model_AutoSlice.3mf") == "model_AutoSlice_2.3mf"


def test_autoslice_output_name_avoids_collision_case_insensitively():
    existing = {"MODEL_AUTOSLICE.3MF", "model_AutoSlice_2.3mf"}
    assert autoslice_output_filename("model.3mf", existing) == "model_AutoSlice_3.3mf"
