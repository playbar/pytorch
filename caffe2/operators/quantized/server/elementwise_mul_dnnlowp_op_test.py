from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import numpy as np
import caffe2.python.hypothesis_test_util as hu
from caffe2.python import core, dyndep
from hypothesis import given
import hypothesis.strategies as st
import collections
from dnnlowp_test_utils import check_quantized_results_close

dyndep.InitOpsLibrary("//caffe2/caffe2/operators/quantized/server:dnnlowp_ops")


class DNNLowPMulOpTest(hu.HypothesisTestCase):
    @given(N=st.integers(32, 256),
           in_quantized=st.booleans(),
           out_quantized=st.booleans(),
           in_place=st.sampled_from([
               (False, False), (True, False), (False, True)]),
           **hu.gcs_cpu_only)
    def test_dnnlowp_elementwise_mul_int(self, N,
                                         in_quantized, out_quantized, in_place,
                                         gc, dc):
        # FIXME: DNNLOWP Mul doesn't support inplace operation and
        # dequantize_output=1 at the same time
        if in_place[0] or in_place[1]:
            in_quantized = True
            out_quantized = True

        # All inputs have scale 1, so exactly represented after quantization
        min_ = -100
        max_ = min_ + 255
        A = np.round(np.random.rand(N) * (max_ - min_) + min_)
        A = A.astype(np.float32)
        A[0] = min_
        A[1] = max_

        B = np.round(np.random.rand(N) * 255 - 128).astype(np.float32)
        B[0] = -128
        B[1] = 127

        Output = collections.namedtuple("Output", ["Y", "engine"])
        outputs = []

        engine_list = ['', 'DNNLOWP']
        for engine in engine_list:
            net = core.Net("test_net")

            do_quantize = "DNNLOWP" in engine and in_quantized
            do_dequantize = "DNNLOWP" in engine and out_quantized

            if do_quantize:
                quantize_A = core.CreateOperator(
                    "Quantize",
                    ['A'], ['A_q'],
                    engine=engine,
                    device_option=gc,
                )
                net.Proto().op.extend([quantize_A])

                quantize_B = core.CreateOperator(
                    "Quantize",
                    ['B'], ['B_q'],
                    engine=engine,
                    device_option=gc,
                )
                net.Proto().op.extend([quantize_B])

            out = 'Y'
            if in_place[0]:
                out = 'A'
            elif in_place[1]:
                out = 'B'

            mul = core.CreateOperator(
                "Mul",
                ['A_q', 'B_q'] if do_quantize else ['A', 'B'],
                [(out + '_q') if do_dequantize else out],
                dequantize_output=not do_dequantize,
                engine=engine,
                device_option=gc,
            )
            net.Proto().op.extend([mul])

            if do_dequantize:
                dequantize = core.CreateOperator(
                    "Dequantize",
                    [out + '_q'],
                    [out],
                    engine=engine,
                    device_option=gc,
                )
                net.Proto().op.extend([dequantize])

            self.ws.create_blob('A').feed(A, device_option=gc)
            self.ws.create_blob('B').feed(B, device_option=gc)
            self.ws.run(net)
            outputs.append(Output(Y=self.ws.blobs[out].fetch(), engine=engine))

        check_quantized_results_close(outputs)

    @given(**hu.gcs_cpu_only)
    def test_dnnlowp_elementwise_mul_broadcast(self, gc, dc):
        # Set broadcast and no axis, i.e. broadcasting last dimensions.
        min_ = -100
        max_ = min_ + 255
        A = np.round(np.random.rand(2, 3, 4, 5) * (max_ - min_) + min_)
        A = A.astype(np.float32)
        A[0, 0, 0, 0] = min_
        A[0, 0, 0, 1] = max_

        B = np.round(np.random.rand(4, 5) * 255 - 128).astype(np.float32)
        B[0, 0] = -128
        B[0, 1] = 127

        Output = collections.namedtuple("Output", ["Y", "engine"])
        outputs = []

        engine_list = ['', 'DNNLOWP']
        for engine in engine_list:
            net = core.Net("test_net")

            mul = core.CreateOperator(
                "Mul",
                ['A', 'B'],
                ['Y'],
                engine=engine,
                device_option=gc,
                broadcast=1,
                dequantize_output=1,
            )
            net.Proto().op.extend([mul])

            self.ws.create_blob('A').feed(A, device_option=gc)
            self.ws.create_blob('B').feed(B, device_option=gc)
            self.ws.run(net)
            outputs.append(Output(
                Y=self.ws.blobs["Y"].fetch(), engine=engine))

        check_quantized_results_close(outputs)

    @given(**hu.gcs_cpu_only)
    def test_dnnlowp_elementwise_mul_broadcast_axis(self, gc, dc):
        for bdim, axis in [
                ((3, 4), 1),      # broadcasting intermediate dimensions
                ((2,), 0),        # broadcasting the first dimension
                ((1, 4, 1), 1)]:
                # broadcasting with single elem dimensions at both ends

            min_ = -100
            max_ = min_ + 255
            A = np.round(np.random.rand(2, 3, 4, 5) * (max_ - min_) + min_)
            A = A.astype(np.float32)

            B = np.round(np.random.rand(*bdim) * 255 - 128).astype(np.float32)

            A.flat[0] = min_
            A.flat[1] = max_
            B.flat[0] = -128
            B.flat[1] = 127

            Output = collections.namedtuple("Output", ["Y", "engine"])
            outputs = []

            engine_list = ['', 'DNNLOWP']
            for engine in engine_list:
                net = core.Net("test_net")

                mul = core.CreateOperator(
                    "Mul",
                    ['A', 'B'],
                    ['Y'],
                    engine=engine,
                    device_option=gc,
                    broadcast=1,
                    axis=axis,
                    dequantize_output=1,
                )
                net.Proto().op.extend([mul])

                self.ws.create_blob('A').feed(A, device_option=gc)
                self.ws.create_blob('B').feed(B, device_option=gc)
                self.ws.run(net)
                outputs.append(Output(
                    Y=self.ws.blobs["Y"].fetch(), engine=engine))

            check_quantized_results_close(outputs)
