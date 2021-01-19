# Copyright 2021, Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import pandas as pd
import tensorflow as tf
from fedopt_guide.stackoverflow_transformer import centralized_main


class CentralizedMainTest(tf.test.TestCase):

  def test_run_centralized(self):
    num_epochs = 1
    batch_size = 16
    root_output_dir = self.create_tempdir()
    exp_name = 'test_run_centralized'

    centralized_main.run_centralized(
        tf.keras.optimizers.SGD(learning_rate=0.01),
        num_epochs,
        batch_size,
        vocab_size=10,
        d_embed=2,
        d_model=2,
        d_hidden=2,
        num_heads=1,
        num_layers=1,
        experiment_name=exp_name,
        root_output_dir=root_output_dir,
        max_batches=100)

    self.assertTrue(tf.io.gfile.exists(root_output_dir))
    log_dir = os.path.join(root_output_dir, 'logdir', exp_name)
    train_log_dir = os.path.join(log_dir, 'train')
    validation_log_dir = os.path.join(log_dir, 'validation')
    self.assertTrue(tf.io.gfile.exists(log_dir))
    self.assertTrue(tf.io.gfile.exists(train_log_dir))
    self.assertTrue(tf.io.gfile.exists(validation_log_dir))

    results_dir = os.path.join(root_output_dir, 'results', exp_name)
    self.assertTrue(tf.io.gfile.exists(results_dir))
    metrics_file = os.path.join(results_dir, 'metric_results.csv')
    self.assertTrue(tf.io.gfile.exists(metrics_file))

    metrics_csv = pd.read_csv(metrics_file)
    self.assertLen(
        metrics_csv.index,
        num_epochs,
        msg='The output metrics CSV should have {} rows, equal to the number of'
        'training epochs.'.format(num_epochs))

    self.assertIn(
        'loss',
        metrics_csv.columns,
        msg='The output metrics CSV should have a column "loss" if training is'
        'successful.')
    self.assertIn(
        'val_loss',
        metrics_csv.columns,
        msg='The output metrics CSV should have a column "val_loss" if '
        'validation metric computation is successful.')


if __name__ == '__main__':
  tf.test.main()
