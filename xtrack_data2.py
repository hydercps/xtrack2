from collections import defaultdict
import json
import os
import re
import h5py
import numpy as np
import math

import data_model



word_re = re.compile(r'([A-Za-z]+)')


def tokenize(text):
    for match in word_re.finditer(text):
        yield match.group(1)


class XTrackData2(object):
    attrs_to_save = ['sequences', 'labels', 'labels_seq_id', 'labels_time',
                     'vocab', 'vocab_rev', 'classes', 'slots']

    null_class = '_null_'

    def _init(self, slots, vocab_from):
        self.slots = slots
        if vocab_from:
            data = XTrackData2.load(vocab_from)
            self.vocab = data.vocab
            self.vocab_rev = data.vocab_rev
            self.classes = data.classes
            self.vocab_fixed = True
        else:
            self.vocab = {
                "#NOTHING": 0,
                "#EOS": 1,
                "#OOV": 2,
            }

            self.vocab_rev = {
                val: key for key, val in self.vocab.iteritems()
            }

            self.classes = {}
            for slot in slots:
                self.classes[slot] = {self.null_class: 0}

            self.vocab_fixed = False


    def build(self, dialogs, slots, vocab_from):
        self._init(slots, vocab_from)

        self.sequences = []

        self.labels = {slot: [] for slot in slots}
        self.labels_seq_id = []
        self.labels_time = []
        for dialog_ndx, dialog in enumerate(dialogs):
            seq = []
            for msg, state, actor in zip(dialog.messages,
                                         dialog.states,
                                         dialog.actors):
                token_seq = list(tokenize(msg.lower()))

                # We do not like empty messages or system messages now.
                if len(token_seq) == 0 or actor == \
                        data_model.Dialog.ACTOR_SYSTEM:
                    continue

                token_seq.append('#EOS')
                for i, token in enumerate(token_seq):
                    token_ndx = self.get_token_ndx(token)
                    seq.append(token_ndx)

                for slot, val in zip(slots, self.state_to_cls(state, slots)):
                    self.labels[slot].append(val)
                self.labels_seq_id.append(dialog_ndx)
                self.labels_time.append(len(seq) - 1)

            if len(seq) > 0:
                self.sequences.append(seq)

    def get_token_ndx(self, token):
        if token in self.vocab:
            return self.vocab[token]
        else:
            if not self.vocab_fixed:
                self.vocab[token] = res = len(self.vocab)
                self.vocab_rev[self.vocab[token]] = token
                return res
            else:
                return self.vocab['#OOV']

    def state_to_cls(self, state, slots):
        res = []
        for slot in slots:
            res.append(self.state_to_cls_for(state, slot))

        return res

    def state_to_cls_for(self, state, slot):
        if not state:
            return self.classes[slot][self.null_class]
        else:
            value = state.get(slot)

            if value:
                food = next(tokenize(value))

                if self.vocab_fixed:
                    if not food in self.classes[slot]:
                        res = self.classes[slot][self.null_class]
                    else:
                        res = self.classes[slot][food]
                else:
                    if not food in self.classes[slot]:
                        self.classes[slot][food] = len(self.classes[slot])
                    res = self.classes[slot][food]

            else:
                res = self.classes[slot][self.null_class]

            return res

    def save(self, out_file):
        with open(out_file, 'w') as f_out:
            obj = {}
            for attr in self.attrs_to_save:
                obj[attr] = getattr(self, attr)

            json.dump(obj, f_out, indent=4)

    @classmethod
    def load(cls, in_file):
        with open(in_file, 'r') as f_in:
            data = json.load(f_in)

        xtd = XTrackData2()
        for attr in cls.attrs_to_save:
            val = data[attr]
            setattr(xtd, attr, val)

        return xtd


if __name__ == '__main__':
    from utils import pdb_on_error
    pdb_on_error()

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--data_dir', required=True)
    parser.add_argument('--out_file', required=True)
    parser.add_argument('--vocab_from', type=str, required=False, default=None)
    parser.add_argument('--slots', default='food')

    args = parser.parse_args()

    dialogs = []
    for f_name in os.listdir(args.data_dir):
        if f_name.endswith('.json'):
            dialogs.append(
                model.Dialog.deserialize(
                    open(os.path.join(args.data_dir, f_name)).read()
                )
            )

    slots = args.slots.split(',')
    print slots

    xtd = XTrackData2()
    xtd.build(dialogs=dialogs, vocab_from=args.vocab_from, slots=slots)
    xtd.save(args.out_file)

