# Copyright 2020, Google LLC.
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

"""Runs federated training on various tasks using a generalized form of FedAvg.
Specifically, we create (according to flags) an iterative processes that allows
for client and server learning rate schedules, as well as various client and
server optimization methods. For more details on the learning rate scheduling
and optimization methods, see `shared/optimizer_utils.py`.
Uses the tff.learning.build_federated_averaging_process to perform federated
averaging on the clients.
"""

import collections
from typing import Any, Callable, Optional

from absl import app
from absl import flags
import tensorflow as tf
import tensorflow_federated as tff

from fedopt_guide.cifar10 import federated_cifar10
from optimization.shared import optimizer_utils
from utils import utils_impl

_SUPPORTED_TASKS = [
    'cifar10'
]

with utils_impl.record_hparam_flags() as optimizer_flags:
  # Defining optimizer flags
  optimizer_utils.define_optimizer_flags('client')
  optimizer_utils.define_optimizer_flags('server')
  optimizer_utils.define_lr_schedule_flags('client')
  optimizer_utils.define_lr_schedule_flags('server')

with utils_impl.record_hparam_flags() as shared_flags:
  # Federated training hyperparameters
  flags.DEFINE_integer('client_epochs_per_round', 1,
                       'Number of epochs in the client to take per round.')
  flags.DEFINE_integer('client_batch_size', 20, 'Batch size on the clients.')
  flags.DEFINE_integer('clients_per_round', 10,
                       'How many clients to sample per round.')
  flags.DEFINE_integer('client_datasets_random_seed', 1,
                       'Random seed for client sampling.')

  # Training loop configuration
  flags.DEFINE_string(
      'experiment_name', None, 'The name of this experiment. Will be append to '
      '--root_output_dir to separate experiment results.')
  flags.mark_flag_as_required('experiment_name')
  flags.DEFINE_string('root_output_dir', '/tmp/fed_opt/',
                      'Root directory for writing experiment output.')
  flags.DEFINE_integer('total_rounds', 200, 'Number of total training rounds.')
  flags.DEFINE_integer(
      'rounds_per_eval', 1,
      'How often to evaluate the global model on the validation dataset.')
  flags.DEFINE_integer('rounds_per_checkpoint', 50,
                       'How often to checkpoint the global model.')
  flags.DEFINE_integer(
      'rounds_per_profile', 0,
      '(Experimental) How often to run the experimental TF profiler, if >0.')

with utils_impl.record_hparam_flags() as cifar10_flags:
  # CIFAR-10 flags
  flags.DEFINE_integer('cifar10_crop_size', 24, 'The height and width of '
                       'images after preprocessing.')


FLAGS = flags.FLAGS

TASK_FLAGS = collections.OrderedDict(
    cifar10=cifar10_flags)

TASK_FLAG_PREFIXES = collections.OrderedDict(
    cifar10='cifar10')


def _get_hparam_flags():
  """Returns an ordered dictionary of pertinent hyperparameter flags."""
  hparam_dict = utils_impl.lookup_flag_values(shared_flags)

  # Update with optimizer flags corresponding to the chosen optimizers.
  opt_flag_dict = utils_impl.lookup_flag_values(optimizer_flags)
  opt_flag_dict = optimizer_utils.remove_unused_flags('client', opt_flag_dict)
  opt_flag_dict = optimizer_utils.remove_unused_flags('server', opt_flag_dict)
  hparam_dict.update(opt_flag_dict)

  # Update with task-specific flags.
  task_name = FLAGS.task
  if task_name in TASK_FLAGS:
    task_hparam_dict = utils_impl.lookup_flag_values(TASK_FLAGS[task_name])
    hparam_dict.update(task_hparam_dict)

  return hparam_dict


def _get_task_args():
  """Returns an ordered dictionary of task-specific arguments.
  This method returns a dict of (arg_name, arg_value) pairs, where the
  arg_name has had the task name removed as a prefix (if it exists), as well
  as any leading `-` or `_` characters.
  Returns:
    An ordered dictionary of (arg_name, arg_value) pairs.
  """
  task_name = FLAGS.task
  task_args = collections.OrderedDict()

  if task_name in TASK_FLAGS:
    task_flag_list = TASK_FLAGS[task_name]
    task_flag_dict = utils_impl.lookup_flag_values(task_flag_list)
    task_flag_prefix = TASK_FLAG_PREFIXES[task_name]
    for (key, value) in task_flag_dict.items():
      if key.startswith(task_flag_prefix):
        key = key[len(task_flag_prefix):].lstrip('_-')
      task_args[key] = value
  return task_args


def main(argv):
  if len(argv) > 1:
    raise app.UsageError('Expected no command-line arguments, '
                         'got: {}'.format(argv))

  client_optimizer_fn = optimizer_utils.create_optimizer_fn_from_flags('client')
  server_optimizer_fn = optimizer_utils.create_optimizer_fn_from_flags('server')

  client_lr_schedule = optimizer_utils.create_lr_schedule_from_flags('client')
  server_lr_schedule = optimizer_utils.create_lr_schedule_from_flags('server')

  def iterative_process_builder(
      model_fn: Callable[[], tff.learning.Model],
      client_weight_fn: Optional[Callable[[Any], tf.Tensor]] = None,
  ) -> tff.templates.IterativeProcess:

    """Creates an iterative process using a given TFF `model_fn`.

    Args:
      model_fn: A no-arg function returning a `tff.learning.Model`.
      client_weight_fn: Optional function that takes the output of
        `model.report_local_outputs` and returns a tensor providing the weight
        in the federated average of model deltas. If not provided, the default
        is the total number of examples processed on device.

    Returns:
      A `tff.templates.IterativeProcess`.
    """

    return tff.learning.build_federated_averaging_process(
        model_fn=model_fn,
        client_optimizer_fn=client_optimizer_fn,
        server_optimizer_fn=server_optimizer_fn,
        client_weighting=client_weight_fn, 
        use_experimental_simulation_loop=True)

  shared_args = utils_impl.lookup_flag_values(shared_flags)
  shared_args['iterative_process_builder'] = iterative_process_builder
  task_args = _get_task_args()
  hparam_dict = _get_hparam_flags()

  run_federated_fn = federated_cifar10.run_federated

  run_federated_fn(**shared_args, **task_args, hparam_dict=hparam_dict)


if __name__ == '__main__':
  app.run(main)
