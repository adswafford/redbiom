import unittest
import requests

import biom
import pandas as pd
import pandas.util.testing as pdt

import redbiom.admin
import redbiom.fetch
from redbiom.fetch import (_biom_from_samples, sample_metadata,
                           sample_counts_per_category)


table = biom.load_table('test.biom')
metadata = pd.read_csv('test.txt', sep='\t', dtype=str)


class FetchTests(unittest.TestCase):
    def setUp(self):
        host = redbiom.get_config()['hostname']
        req = requests.get(host + '/FLUSHALL')
        assert req.status_code == 200

    def test_biom_from_samples(self):
        redbiom.admin.create_context('test', 'a nice test')
        redbiom.admin.load_sample_metadata(metadata)
        redbiom.admin.load_sample_data(table, 'test', tag=None)
        q = ('TACGGAGGATCCGAGCGTTATCCGGATTTATTGGGTTTAAAGGGAGCGTAGGCGGGTTGTTAA'
             'GTCAGTTGTGAAAGTTTGCGGCTCAACCGTAAATTTG')
        qidx = table.index(q, axis='observation')
        exp = table.filter(lambda v, i, md: v[qidx] > 0, inplace=False)
        exp.filter(lambda v, i, md: sum(v > 0) > 0, axis='observation')

        fetch = exp.ids()[:]

        exp_map = {k: ["UNTAGGED_%s" % k] for k in exp.ids()}
        exp.update_ids({k: "%s.UNTAGGED" % k for k in exp.ids()})

        obs, obs_map = _biom_from_samples('test', fetch)
        obs = obs.sort_order(exp.ids(axis='observation'), axis='observation')
        self.assertEqual(obs, exp)
        self.assertEqual(obs_map, exp_map)

    def test_sample_metadata_samples_not_represented_in_context(self):
        redbiom.admin.create_context('test', 'a nice test')
        redbiom.admin.load_sample_metadata(metadata)
        with self.assertRaisesRegexp(ValueError,
                                     "None of the samples"):
            # sample data have not been loaded into the context
            sample_metadata(['10317.000047188', '10317.000046868'],
                            context='test')

    def test_sample_metadata_all_cols(self):
        redbiom.admin.load_sample_metadata(metadata)
        exp = metadata.copy()
        exp.set_index('#SampleID', inplace=True)
        obs, ambig = sample_metadata(table.ids(), common=False)
        obs.set_index('#SampleID', inplace=True)
        self.assertEqual(sorted(exp.index), sorted(obs.index))
        self.assertTrue(set(obs.columns).issubset(exp.columns))

        for col in set(exp.columns) - set(obs.columns):
            self.assertTrue(set(exp[col].values), {'Unspecified', })
        obs = obs.loc[exp.index]

        # we cannot do a full table == table test. Round tripping is not
        # assured as we do not store null values in redbiom, and there is a
        # litany of possible null values.
        pdt.assert_series_equal(obs['BMI'], exp['BMI'])
        obs['AGE_YEARS'] = [v if v is not None else 'Unknown'
                            for v in obs['AGE_YEARS']]
        pdt.assert_series_equal(obs['AGE_YEARS'], exp['AGE_YEARS'])
        pdt.assert_series_equal(obs['SAMPLE_TYPE'], exp['SAMPLE_TYPE'])

    def test_sample_metadata_have_data(self):
        redbiom.admin.load_sample_metadata(metadata)
        exp = metadata.copy()
        exp.set_index('#SampleID', inplace=True)
        obs, ambig = sample_metadata(table.ids(), common=True)
        self.assertEqual(sorted(exp.index), sorted(obs.index))
        self.assertNotEqual(sorted(exp.columns), sorted(obs.columns))
        obs = obs.loc[exp.index]

        # we cannot do a full table == table test. Round tripping is not
        # assured as we do not store null values in redbiom, and there is a
        # litany of possible null values.
        pdt.assert_series_equal(obs['BMI'], exp['BMI'])
        pdt.assert_series_equal(obs['SAMPLE_TYPE'], exp['SAMPLE_TYPE'])

        # one sample has "Unknown" as its AGE_YEARS value. This means that
        # it is not informative for that column, so that value is not stored
        # for that sample. As a result, the AGE_YEARS columns is not considered
        # to be represented across all samples
        self.assertNotIn('AGE_YEARS', obs.columns)

    def test_sample_metadata_context(self):
        redbiom.admin.create_context('test', 'a nice test')
        redbiom.admin.load_sample_metadata(metadata)
        redbiom.admin.load_sample_data(table, 'test', tag='foo')

        exp = metadata.copy()
        exp.set_index('#SampleID', inplace=True)
        exp.index = ["%s.foo" % i for i in exp.index]

        obs, ambig = sample_metadata(table.ids(), common=False, context='test')
        obs.set_index('#SampleID', inplace=True)

        self.assertEqual(sorted(exp.index), sorted(obs.index))
        self.assertTrue(set(obs.columns).issubset(exp.columns))

        for col in set(exp.columns) - set(obs.columns):
            self.assertTrue(set(exp[col].values), {'Unspecified', })
        obs = obs.loc[exp.index]

        # we cannot do a full table == table test. Round tripping is not
        # assured as we do not store null values in redbiom, and there is a
        # litany of possible null values.
        pdt.assert_series_equal(obs['BMI'], exp['BMI'])
        obs['AGE_YEARS'] = [v if v is not None else 'Unknown'
                            for v in obs['AGE_YEARS']]
        pdt.assert_series_equal(obs['AGE_YEARS'], exp['AGE_YEARS'])
        pdt.assert_series_equal(obs['SAMPLE_TYPE'], exp['SAMPLE_TYPE'])

    def test_sample_metadata_restrict(self):
        redbiom.admin.load_sample_metadata(metadata)
        exp = metadata.copy()
        exp.set_index('#SampleID', inplace=True)
        exp = exp[['BMI', 'AGE_YEARS']]
        exp = exp.sort_values('BMI')
        obs, ambig = sample_metadata(table.ids(),
                                     restrict_to=['BMI', 'AGE_YEARS'])
        obs.set_index('#SampleID', inplace=True)
        obs = obs.sort_values('BMI')
        obs = obs[['BMI', 'AGE_YEARS']]
        obs['AGE_YEARS'] = [v if v is not None else 'Unknown'
                            for v in obs['AGE_YEARS']]
        pdt.assert_frame_equal(obs, exp)

    def test_sample_metadata_restrict_bad_cols(self):
        redbiom.admin.load_sample_metadata(metadata)
        with self.assertRaises(KeyError):
            sample_metadata(table.ids(), restrict_to=['BMI', 'foo'])

    def test_sample_counts_per_category(self):
        redbiom.admin.load_sample_metadata(metadata)
        obs = sample_counts_per_category()
        self.assertEqual(len(obs), 525)
        self.assertEqual(obs['LATITUDE'], 10)

    def test_sample_counts_per_category_specific(self):
        redbiom.admin.load_sample_metadata(metadata)
        obs = sample_counts_per_category(['LATITUDE'])
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs['LATITUDE'], 10)

        obs = sample_counts_per_category(['LATITUDE', 'LONGITUDE'])
        self.assertEqual(len(obs), 2)
        self.assertEqual(obs['LATITUDE'], 10)
        self.assertEqual(obs['LONGITUDE'], 10)


if __name__ == '__main__':
    unittest.main()
