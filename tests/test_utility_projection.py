import unittest
from adapters.utilities import component_record


class ProjectionTests(unittest.TestCase):
    def test_shared_renderer_preserves_identifiers_and_missing_values(self):
        value=component_record(dict(number='0012',street='Café',street_type='ST',unit_prefix='APT',unit='03',city='Example',state='NY',postal_code='00123'), 'address_normalizer')
        self.assertEqual(value,dict(address_line_1='0012 CAFÉ ST',address_line_2='APT 03',city='EXAMPLE',state='NY',postal_code='00123'))

    def test_renderer_does_not_repair_abbreviations_or_zip_width(self):
        value=component_record(dict(street_number='12',street_name='Alder',street_suffix='Street',zip5='0123',zip4='0002'),'doorplate')
        self.assertEqual(value['address_line_1'],'12 ALDER STREET')
        self.assertEqual(value['postal_code'],'0123-0002')
        self.assertIsNone(value['address_line_2'])


if __name__=='__main__':unittest.main()
