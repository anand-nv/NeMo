# Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import re
from typing import Any, Dict, Optional

import torch
import torch.nn as nn
from omegaconf.dictconfig import DictConfig
from pytorch_lightning.trainer.trainer import Trainer

from nemo.collections.nlp.data.language_modeling.megatron.data_samplers import (
    MegatronPretrainingRandomSampler,
    MegatronPretrainingSampler,
)
from nemo.collections.nlp.data.language_modeling.megatron.dataset_utils import build_train_valid_test_datasets
from nemo.collections.nlp.models.language_modeling.megatron_lm_encoder_decoder_model import MegatronLMEncoderDecoderModule
from nemo.collections.nlp.models.nlp_model import NLPModel
from nemo.collections.nlp.modules.common.megatron.clip_grads import clip_grad_norm_fp32
from nemo.collections.nlp.modules.common.megatron.megatron_init import initialize_model_parallel_for_nemo
from nemo.collections.nlp.modules.common.megatron.utils import average_losses_across_data_parallel_group
from nemo.collections.nlp.modules.common.tokenizer_utils import get_nmt_tokenizer
from nemo.utils import AppState, logging

try:
    from apex.transformer import parallel_state, tensor_parallel

    HAVE_APEX = True
except (ImportError, ModuleNotFoundError):
    HAVE_APEX = False

__all__ = ["MegatronT5Model"]

class MegatronT5Model(MegatronLMEncoderDecoderModule):
    """
    Megatron T5 pretraining
    """

    def __init__(self, cfg: DictConfig, trainer: Trainer):
        if not HAVE_APEX:
            raise ImportError(
                "Apex was not found. Please see the NeMo README for installation instructions: https://github.com/NVIDIA/NeMo#megatron-gpt."
            )
        super().__init__(cfg, trainer=trainer)
<<<<<<< HEAD

    def _build_vocab(self):
        # T5-related construction
=======
        self.cfg = cfg

        # used in NVIDIA NGC PyTorch containers
        self._enable_nvidia_optimizations()

        if self.cfg.get('use_cpu_initialization', False) is False:
            torch.cuda.set_device(trainer.local_rank)

        # buffer used during train_step for logging average loss over gradient accumulation steps
        self._reduced_loss_buffer = []

        initialize_model_parallel_for_nemo(
            world_size=trainer.world_size,
            global_rank=trainer.global_rank,
            local_rank=trainer.local_rank,
            tensor_model_parallel_size=cfg.get('tensor_model_parallel_size', 1),
            seed=self.cfg.get('seed', 1234),
        )

        self.tokenizer = get_nmt_tokenizer(
            library=self.cfg.tokenizer.library,
            model_name=self.cfg.tokenizer.type,
            tokenizer_model=self.register_artifact("tokenizer_model", self.cfg.tokenizer.model),
            vocab_file=self.register_artifact("vocab_file", self.cfg.tokenizer.vocab_file),
            merges_file=self.register_artifact("merges_file", self.cfg.tokenizer.merge_file),
            legacy=self.cfg.tokenizer.library == "sentencepiece",
        )
>>>>>>> c743cbf5871a4ede7b6a1ee8aa0004ba2a05717a
        self.num_sentinel_tokens = self.cfg.tokenizer.num_sentinel_tokens
        self._add_special_tokens_to_tokenizer()

        super()._build_vocab()


    def _add_special_tokens_to_tokenizer(self):
        if self.cfg.tokenizer.library == 'huggingface' or self.cfg.tokenizer.library == 'megatron':
            additional_tokens = {
                'additional_special_tokens': [f'<extra_id_{i}>' for i in range(self.num_sentinel_tokens)]
            }
            self.tokenizer.add_special_tokens(additional_tokens)

        if self.cfg.tokenizer.library == 'sentencepiece':
            # Need to add cls, sep, mask tokens to the tokenizer if they don't exist.
            # If cls, sep and mask are not attributes of the tokenizer, add it.
            if not hasattr(self.tokenizer, 'cls_token'):
                self.tokenizer.add_special_tokens({'cls_token': '<cls>'})
            if not hasattr(self.tokenizer.tokenizer, 'sep_id'):
                self.tokenizer.add_special_tokens({'sep_token': '<sep>'})
            if not hasattr(self.tokenizer.tokenizer, 'mask_id'):
                self.tokenizer.add_special_tokens({'mask_token': '<mask>'})

            # bos, eos, pad and unk may be present in the provided spm .model file, if they are, use it.
            if not hasattr(self.tokenizer, 'pad_token'):
                if hasattr(self.tokenizer.tokenizer, 'pad_id') and self.tokenizer.tokenizer.pad_id() > 0:
                    self.tokenizer.pad_token = self.tokenizer.tokenizer.id_to_piece(self.tokenizer.tokenizer.pad_id())
                else:
                    self.tokenizer.add_special_tokens({'pad_token': '<pad>'})
            else:
                self.tokenizer.add_special_tokens({'pad_token': '<pad>'})

            if not hasattr(self.tokenizer, 'bos_token'):
                if hasattr(self.tokenizer.tokenizer, 'bos_id') and self.tokenizer.tokenizer.bos_id() > 0:
                    self.tokenizer.bos_token = self.tokenizer.tokenizer.id_to_piece(self.tokenizer.tokenizer.bos_id())
                else:
                    self.tokenizer.add_special_tokens({'bos_token': '<bos>'})
            else:
                self.tokenizer.add_special_tokens({'bos_token': '<s>'})

            if not hasattr(self.tokenizer, 'eos_token'):
                if hasattr(self.tokenizer.tokenizer, 'eos_id') and self.tokenizer.tokenizer.eos_id() > 0:
                    self.tokenizer.eos_token = self.tokenizer.tokenizer.id_to_piece(self.tokenizer.tokenizer.eos_id())
                else:
                    self.tokenizer.add_special_tokens({'eos_token': '<eos>'})
            else:
                self.tokenizer.add_special_tokens({'eos_token': '</s>'})

            # Special check to see if <extra_id_{}> is already present in the tokenizer. If it is, only modify the additional_special_tokens function.
            for i in range(self.num_sentinel_tokens):
                if f'▁<extra_id_{i}>' in self.tokenizer.vocab:
                    self.tokenizer.special_token_to_id[f'<extra_id_{i}>'] = self.tokenizer.text_to_ids(
                        f'<extra_id_{i}>'
                    )[0]
                else:
                    self.tokenizer.add_special_tokens([f'<extra_id_{i}>'])


    def build_train_valid_test_datasets(self):
        logging.info('Building T5 datasets.')
        if self.cfg.data.seq_length_dec < self.cfg.data.seq_length * self.cfg.data.masked_lm_prob:
            raise ValueError(
                f"Cannot have decoder max sequence length ({self.cfg.data.seq_length_dec}) less than encoder sequence length ({self.cfg.data.seq_length}) * masked_lm_prob ({self.cfg.data.masked_lm_prob})"
            )
        global_batch_size = self.trainer.world_size * self.cfg.micro_batch_size / self.cfg.tensor_model_parallel_size
        eval_iters = (self.trainer.max_steps // self.trainer.val_check_interval + 1) * self.trainer.limit_val_batches
        test_iters = self.trainer.limit_test_batches
        train_valid_test_num_samples = [
            self.trainer.max_steps * global_batch_size,
            eval_iters * global_batch_size,
            test_iters * global_batch_size,
        ]
        self._train_ds, self._validation_ds, self._test_ds = build_train_valid_test_datasets(
            cfg=self.cfg,
            trainer=self.trainer,
            tokenizer=self.tokenizer,
            data_prefix=self.cfg.data.data_prefix,
            data_impl=self.cfg.data.data_impl,
            splits_string=self.cfg.data.splits_string,
            train_valid_test_num_samples=train_valid_test_num_samples,
            max_seq_length=self.cfg.data.seq_length,
            max_seq_length_dec=self.cfg.data.seq_length_dec,
            masked_lm_prob=self.cfg.data.masked_lm_prob,
            short_seq_prob=self.cfg.data.short_seq_prob,
            seed=self.cfg.seed,
            skip_warmup=self.cfg.data.skip_warmup,
            dataset_type='t5',
        )
        logging.info(f'Length of train dataset: {len(self._train_ds)}')
        logging.info(f'Length of val dataset: {len(self._validation_ds)}')
        logging.info(f'Length of test dataset: {len(self._test_ds)}')
        logging.info(f'Finished building T5 datasets.')
        return self._train_ds, self._validation_ds, self._test_ds

<<<<<<< HEAD
=======
    def build_pretraining_data_loader(self, dataset, consumed_samples):
        """Buld dataloader given an input dataset."""

        if dataset is None:
            return None

        # Megatron sampler
        if self.cfg.data.dataloader_type == 'single':
            batch_sampler = MegatronPretrainingSampler(
                total_samples=len(dataset),
                consumed_samples=consumed_samples,
                micro_batch_size=self.cfg.micro_batch_size,
                data_parallel_rank=parallel_state.get_data_parallel_rank(),
                data_parallel_size=parallel_state.get_data_parallel_world_size(),
            )
        elif self.cfg.data.dataloader_type == 'cyclic':
            batch_sampler = MegatronPretrainingRandomSampler(
                total_samples=len(dataset),
                consumed_samples=consumed_samples,
                micro_batch_size=self.cfg.micro_batch_size,
                data_parallel_rank=parallel_state.get_data_parallel_rank(),
                data_parallel_size=parallel_state.get_data_parallel_world_size(),
            )
        else:
            raise Exception('{} dataloader type is not supported.'.format(self.cfg.dataloader_type))

        # Torch dataloader.
        return torch.utils.data.DataLoader(
            dataset, batch_sampler=batch_sampler, num_workers=self.cfg.data.num_workers, pin_memory=True,
        )

    def setup(self, stage=None):
        """A PTL method to setup the training, validation and test datasets."""
        if stage == 'predict':
            return
        if self._train_dl is not None and self._validation_dl is not None:
            return
        self.build_train_valid_test_datasets()
        self.setup_training_data(self.cfg.data)
        self.setup_validation_data(self.cfg.data)
        self.setup_test_data(self.cfg.data)

    def setup_training_data(self, cfg):
        if hasattr(self, '_train_ds'):
            resume_checkpoint_path = self.trainer.checkpoint_connector.resume_checkpoint_path
            if resume_checkpoint_path:
                consumed_samples = int(
                    float(re.findall(r"consumed_samples\=([0-9]+.[0-9]+)", resume_checkpoint_path)[0])
                )
            else:
                consumed_samples = 0
            self._train_dl = self.build_pretraining_data_loader(self._train_ds, consumed_samples)

    def setup_validation_data(self, cfg):
        if hasattr(self, '_validation_ds'):
            consumed_samples = 0
            self._validation_dl = self.build_pretraining_data_loader(self._validation_ds, consumed_samples)

    def setup_test_data(self, cfg):
        if hasattr(self, '_test_ds'):
            consumed_samples = 0
            self._test_dl = self.build_pretraining_data_loader(self._test_ds, consumed_samples)

    def compute_consumed_samples(self, global_step):
        app_state = AppState()
        consumed_samples = (
            global_step
            * app_state.data_parallel_size
            * self.cfg.micro_batch_size
            * self.trainer.accumulate_grad_batches
        )
        return int(consumed_samples)

    def configure_gradient_clipping(self, *args, **kwargs):
        """PTL hook to configure gradients.
           We use gradient clipping implementation from megatron-lm.
        """
        clip_val = self.trainer.gradient_clip_val
        if clip_val is None:
            return

        clip_val = float(clip_val)
        if clip_val <= 0:
            return

        parameters = self.model.parameters()
        clip_grad_norm_fp32(parameters=parameters, max_norm=clip_val)

    def predict_step(self, batch: Any, batch_idx: int, dataloader_idx: Optional[int] = None) -> Any:
        request = batch
        response = self.complete(request)
        logging.info(f"response: {response}")
        return response

    def make_inference_attention_mask_3d(self, source_block, target_block, pad_id):
        """
        Returns a 3-dimensional (3-D) attention mask
        :param source_block: 2-D array
        :param target_block: 2-D array
        """
        mask = (target_block[:, None, :] != pad_id) * (source_block[:, :, None] != pad_id)
        return mask

    def make_inference_history_mask_3d(self, block):
        batch, length = block.shape
        arange = torch.arange(length, device=block.device)
        history_mask = (arange[None,] <= arange[:, None])[
            None,
        ]
        history_mask = history_mask.expand(batch, length, length)
        return history_mask

    def decode(self, tokens_enc, enc_mask, num_tokens_to_generate):
        encoder_hidden_states = self(
            encoder_input_ids=tokens_enc,
            decoder_input_ids=None,
            encoder_attn_mask=enc_mask,
            decoder_attn_mask=None,
            encoder_decoder_attn_mask=None,
            tokentype_ids=None,
            lm_labels=None,
            enc_hidden_states=None,
            output_enc_hidden_only=True,
        )
        predicted_tokens_dec = torch.LongTensor([self.tokenizer.bos_id]).unsqueeze(0).to(tokens_enc.device)

        for _ in range(num_tokens_to_generate):
            # Overwrite the decoder token since we want to predict
            enc_dec_mask = self.make_inference_attention_mask_3d(
                predicted_tokens_dec, tokens_enc, self.tokenizer.pad_id
            )
            dec_mask = self.make_inference_attention_mask_3d(
                predicted_tokens_dec, predicted_tokens_dec, self.tokenizer.pad_id
            )
            dec_mask = dec_mask * self.make_inference_history_mask_3d(predicted_tokens_dec)

            enc_dec_mask = enc_dec_mask < 0.5
            dec_mask = dec_mask < 0.5

            output_tensor, _ = self(
                encoder_input_ids=tokens_enc,
                decoder_input_ids=predicted_tokens_dec,
                encoder_attn_mask=enc_mask,
                decoder_attn_mask=dec_mask,
                encoder_decoder_attn_mask=enc_dec_mask,
                tokentype_ids=None,
                lm_labels=None,
                enc_hidden_states=encoder_hidden_states,
                output_enc_hidden_only=False,
            )
            output_tensor = tensor_parallel.gather_from_tensor_model_parallel_region(output_tensor)
            log_probs, token_ids = torch.max(nn.functional.log_softmax(output_tensor, dim=-1), dim=-1)
            predicted_tokens_dec = torch.cat([predicted_tokens_dec, token_ids[:, -1].unsqueeze(1)], 1)
            if token_ids[:, -1] == self.tokenizer.eos_id:
                break

        return predicted_tokens_dec, log_probs

    def complete(self, request: Dict):
        """
            Autoregressively invokes language model in the inference mode
        Args:	
            request: Dictionary with the following fields
                * prompt: a string which text the model should complete.
                * tokens_to_generate: how many tokens to generate while doing prompt completion.
        Returns:	
            response: A python dictionary with the following fields
                * prompt: original text of the prompt
                * tokenized_prompt: list of (str) tokens from prompt
                * completion: a python dictionary with the following subfields:
                    * tokens: a list of triples (token, token_id, log_prob) comprising completion
                    * text: completion text (as a single string)
                
        """
        response = {}
        self.freeze()
        # naive greedy slow loop
        # TODO: add option for BeamSearchDecoder

        response['prompt'] = request['prompt'][0]
        response['completion'] = {}
        tokens_enc = request['masked_sample']

        response['masked_input'] = ' '.join(self.tokenizer.ids_to_tokens(tokens_enc[0]))
        enc_mask = self.make_inference_attention_mask_3d(tokens_enc, tokens_enc, self.tokenizer.pad_id)
        enc_mask = enc_mask < 0.5

        predicted_tokens_ids, log_probs = self.decode(tokens_enc, enc_mask, int(request['tokens_to_generate']))
        predicted_tokens_ids = predicted_tokens_ids.cpu().numpy()[0].tolist()
        log_probs = log_probs.cpu().numpy()[0].tolist()
        if self.tokenizer.eos_id in predicted_tokens_ids:
            idx = predicted_tokens_ids.index(self.tokenizer.eos_id)
            predicted_tokens_ids = predicted_tokens_ids[:idx]
        else:
            predicted_tokens_ids = [id for id in predicted_tokens_ids if id != self.tokenizer.pad_id]
        predicted_tokens_dec = self.tokenizer.ids_to_tokens(predicted_tokens_ids)
        response['completion']['text'] = self.tokenizer.tokens_to_text(predicted_tokens_dec)
        response['completion']['tokens'] = list(zip(predicted_tokens_ids, predicted_tokens_dec, log_probs))
        self.unfreeze()
        return response

    def _vocab_size_with_padding(self, orig_vocab_size, make_vocab_size_divisible_by, tensor_model_parallel_size):
        """Pad vocab size so it is divisible by model parallel size and
        still having GPU friendly size."""

        after = orig_vocab_size
        multiple = make_vocab_size_divisible_by * tensor_model_parallel_size
        while (after % multiple) != 0:
            after += 1
        logging.info(
            f'Padded vocab_size: {after}, original vocab_size: {orig_vocab_size}, dummy tokens: {after - orig_vocab_size}.'
        )
        return after

    def _add_special_tokens_to_tokenizer(self):
        if self.cfg.tokenizer.library == 'huggingface' or self.cfg.tokenizer.library == 'megatron':
            additional_tokens = {
                'additional_special_tokens': [f'<extra_id_{i}>' for i in range(self.num_sentinel_tokens)]
            }
            self.tokenizer.add_special_tokens(additional_tokens)

        if self.cfg.tokenizer.library == 'sentencepiece':
            # Need to add cls, sep, mask tokens to the tokenizer if they don't exist.
            # If cls, sep and mask are not attributes of the tokenizer, add it.
            if not hasattr(self.tokenizer, 'cls_token'):
                self.tokenizer.add_special_tokens({'cls_token': '<cls>'})
            if not hasattr(self.tokenizer.tokenizer, 'sep_id'):
                self.tokenizer.add_special_tokens({'sep_token': '<sep>'})
            if not hasattr(self.tokenizer.tokenizer, 'mask_id'):
                self.tokenizer.add_special_tokens({'mask_token': '<mask>'})

            # bos, eos, pad and unk may be present in the provided spm .model file, if they are, use it.
            if not hasattr(self.tokenizer, 'pad_token'):
                if hasattr(self.tokenizer.tokenizer, 'pad_id') and self.tokenizer.tokenizer.pad_id() > 0:
                    self.tokenizer.pad_token = self.tokenizer.tokenizer.id_to_piece(self.tokenizer.tokenizer.pad_id())
                else:
                    self.tokenizer.add_special_tokens({'pad_token': '<pad>'})
            else:
                self.tokenizer.add_special_tokens({'pad_token': '<pad>'})

            if not hasattr(self.tokenizer, 'bos_token'):
                if hasattr(self.tokenizer.tokenizer, 'bos_id') and self.tokenizer.tokenizer.bos_id() > 0:
                    self.tokenizer.bos_token = self.tokenizer.tokenizer.id_to_piece(self.tokenizer.tokenizer.bos_id())
                else:
                    self.tokenizer.add_special_tokens({'bos_token': '<bos>'})
            else:
                self.tokenizer.add_special_tokens({'bos_token': '<s>'})

            if not hasattr(self.tokenizer, 'eos_token'):
                if hasattr(self.tokenizer.tokenizer, 'eos_id') and self.tokenizer.tokenizer.eos_id() > 0:
                    self.tokenizer.eos_token = self.tokenizer.tokenizer.id_to_piece(self.tokenizer.tokenizer.eos_id())
                else:
                    self.tokenizer.add_special_tokens({'eos_token': '<eos>'})
            else:
                self.tokenizer.add_special_tokens({'eos_token': '</s>'})

            # Special check to see if <extra_id_{}> is already present in the tokenizer. If it is, only modify the additional_special_tokens function.
            for i in range(self.num_sentinel_tokens):
                if f'▁<extra_id_{i}>' in self.tokenizer.vocab:
                    self.tokenizer.special_token_to_id[f'<extra_id_{i}>'] = self.tokenizer.text_to_ids(
                        f'<extra_id_{i}>'
                    )[0]
                else:
                    self.tokenizer.add_special_tokens([f'<extra_id_{i}>'])

>>>>>>> c743cbf5871a4ede7b6a1ee8aa0004ba2a05717a
    def list_available_models():
        pass

    def _enable_nvidia_optimizations(self):
        "These optimizations are present in NVIDIA NGC PyTorch Containers"

        # Version check
        nvidia_torch_version = os.getenv('NVIDIA_PYTORCH_VERSION', None)
        if nvidia_torch_version is not None:
            NVIDIA_TORCH_MAJOR = int(nvidia_torch_version.split('.')[0])
            NVIDIA_TORCH_MINOR = int(nvidia_torch_version.split('.')[1])

            # Apex Persistent layer norm is supported from Nvidia PyTorch container v21.11
            if NVIDIA_TORCH_MAJOR < 21 or (NVIDIA_TORCH_MAJOR == 21 and NVIDIA_TORCH_MINOR < 11):
                self.cfg.persist_layer_norm = False

            if NVIDIA_TORCH_MAJOR >= 21 or (NVIDIA_TORCH_MAJOR == 21 and NVIDIA_TORCH_MINOR >= 11):
                # NVFUSER
                torch._C._jit_set_profiling_executor(True)
                torch._C._jit_set_profiling_mode(True)
                torch._C._jit_override_can_fuse_on_cpu(False)
                torch._C._jit_override_can_fuse_on_gpu(False)
                torch._C._jit_set_texpr_fuser_enabled(False)
                torch._C._jit_set_nvfuser_enabled(True)
                torch._C._debug_set_autodiff_subgraph_inlining(False)

        else:
            # Not a Nvidia container. Dependency check is on users
            pass
