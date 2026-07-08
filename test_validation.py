from app import validate_submission_fields

ok, err = validate_submission_fields({'category': 'ring', 'carat': '1', 'type': 'A',
                                      'gold': '18k', 'weight': 3.5, 'ringSize': 12})
assert err is None and ok['weight'] == 3.5, err

_, err = validate_submission_fields({'category': 'ring', 'carat': '1', 'type': 'A',
                                     'gold': '18k', 'weight': 3.5})  # ring, no size
assert err and 'ringSize' in err

_, err = validate_submission_fields({'category': 'sofa', 'carat': '2', 'type': 'Z',
                                     'gold': 'tin', 'weight': -1})
assert err

_, err = validate_submission_fields({'weight': 'abc'}, partial=True)
assert err and 'weight' in err

ok, err = validate_submission_fields({'weight': 4.2}, partial=True)
assert err is None and ok == {'weight': 4.2}

print("all validation checks passed")
