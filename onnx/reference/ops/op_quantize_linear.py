# SPDX-License-Identifier: Apache-2.0
# pylint: disable=W0221

import numpy as np

from onnx import TensorProto
from onnx.helper import (
    float32_to_floate4m3,
    float32_to_floate5m2,
    np_dtype_to_tensor_dtype,
    tensor_dtype_to_np_dtype,
)
from onnx.reference.custom_element_types import floate4m3, floate5m2
from onnx.reference.op_run import OpRun


class _CommonQuantizeLinear(OpRun):

    float32_to_floate4m3 = np.vectorize(float32_to_floate4m3)
    float32_to_floate5m2 = np.vectorize(float32_to_floate5m2)

    def get_zero_point_type(self, zero_point: np.ndarray) -> int:
        if zero_point.dtype == floate4m3 and zero_point.dtype.descr[0][0] == "e4m3":
            return TensorProto.FLOATE4M3
        if zero_point.dtype == floate5m2 and zero_point.dtype.descr[0][0] == "e5m2":
            return TensorProto.FLOATE5M2
        return np_dtype_to_tensor_dtype(zero_point.dtype)

    def common_run(self, x, y_scale, zero_point=None, axis=1):  # type: ignore
        if len(y_scale.shape) > 1:
            raise RuntimeError("Input 2 must be a vector or a number.")
        if len(y_scale.shape) > 0 and y_scale.size == 1:
            y_scale = y_scale[0]
        if len(y_scale.shape) > 0:
            new_shape = [1 for s in x.shape]
            new_shape[axis] = len(y_scale)
            x = x / y_scale.reshape(new_shape)
        else:
            x = x / y_scale
            new_shape = x.shape  # unused
        if zero_point is not None:
            tensor_type = self.get_zero_point_type(zero_point)

            if len(y_scale.shape) > 0:
                x += zero_point.reshape(new_shape)
            else:
                x += zero_point
            # np.around(x, 0, out=x)
            np.floor(x + 0.5, out=x)
            if tensor_type == TensorProto.UINT8:
                np.clip(x, 0, 255, out=x)
                dtype = tensor_dtype_to_np_dtype(tensor_type)
                return (np.ceil(x).astype(dtype),)
            if tensor_type == TensorProto.INT8:
                np.clip(x, -128, 127, out=x)
                dtype = tensor_dtype_to_np_dtype(tensor_type)
                return (np.ceil(x).astype(dtype),)
            if tensor_type == TensorProto.FLOATE4M3:
                f8 = _CommonQuantizeLinear.float32_to_floate4m3(x)
                return (f8.astype(floate4m3),)  # type: ignore[attr-defined]
            if tensor_type == TensorProto.FLOATE5M2:
                f8 = _CommonQuantizeLinear.float32_to_floate5m2(x)
                return (f8.astype(floate5m2),)  # type: ignore[attr-defined]
            raise RuntimeError(
                f"Unexpected tensor_type for input 2: tensor_type={tensor_type}."
            )

        dtype = np.uint8  # type: ignore[assignment]
        # np.around(x, 0, out=x)
        np.floor(x + 0.5, out=x)
        np.clip(x, 0, 255, out=x)
        return (x.astype(dtype),)


class QuantizeLinear(_CommonQuantizeLinear):
    def _run(self, *args, axis=None):  # type: ignore
        # args: x, y_scale, zero_point
        return self.common_run(*args, axis=axis)  # type: ignore
