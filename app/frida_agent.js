'use strict';

const kernel32 = Process.getModuleByName('kernel32.dll');
const ntdll = Process.getModuleByName('ntdll.dll');

function exportAddress(module, name) {
    const address = Module.getGlobalExportByName(name);
    if (address === null) {
        throw new Error('Missing export: ' + module + '!' + name);
    }
    return address;
}

const GetCommState = new NativeFunction(exportAddress('kernel32.dll', 'GetCommState'), 'bool', ['pointer', 'pointer']);
const GetOverlappedResult = new NativeFunction(
    exportAddress('kernel32.dll', 'GetOverlappedResult'),
    'bool',
    ['pointer', 'pointer', 'pointer', 'bool']
);

const serialHandles = new Map();
const nonSerialHandles = new Set();
const pendingReads = new Map();
const namedHandles = new Map();
const monitoredHandles = new Set();
let filterEnabled = false;
let probeActive = false;
const MAX_CAPTURE_BYTES = 1024 * 1024;

function handleKey(handle) {
    return handle.toString();
}

function isValidHandle(handle) {
    return !handle.isNull() && handle.toString() !== '0xffffffffffffffff' && handle.toString() !== '0xffffffff';
}

function readCommInfo(handle) {
    const key = handleKey(handle);
    if (serialHandles.has(key)) {
        return serialHandles.get(key);
    }
    if (nonSerialHandles.has(key)) {
        return null;
    }

    // DCB is 28 bytes on Windows. Allocate extra space to remain ABI-safe.
    const dcb = Memory.alloc(64);
    dcb.writeU32(28);
    const ok = GetCommState(handle, dcb);
    if (!ok) {
        nonSerialHandles.add(key);
        return null;
    }

    const baudRate = dcb.add(4).readU32();
    const byteSize = dcb.add(18).readU8();
    const parityCode = dcb.add(19).readU8();
    const stopBitsCode = dcb.add(20).readU8();
    const parity = ['N', 'O', 'E', 'M', 'S'][parityCode] || '?';
    const stopBits = stopBitsCode === 0 ? '1' : (stopBitsCode === 1 ? '1.5' : '2');
    const info = {
        baudRate: baudRate,
        frame: byteSize + parity + stopBits
    };
    serialHandles.set(key, info);
    return info;
}

function endpointFor(handle) {
    return namedHandles.get(handleKey(handle)) || ('已打开串口 · 句柄 ' + handleKey(handle));
}

function shouldCapture(handle) {
    return !filterEnabled || monitoredHandles.has(handleKey(handle));
}

function emitSerial(direction, handle, buffer, length) {
    if (!shouldCapture(handle) || length <= 0 || buffer.isNull()) {
        return;
    }
    const info = readCommInfo(handle);
    if (info === null) {
        return;
    }
    try {
        const captureLength = Math.min(length, MAX_CAPTURE_BYTES);
        const bytes = buffer.readByteArray(captureLength);
        send({
            type: 'serial',
            direction: direction,
            endpoint: endpointFor(handle),
            baudRate: info.baudRate,
            frame: info.frame
        }, bytes);
    } catch (error) {
        send({ type: 'diagnostic', message: '读取捕获缓冲区失败：' + error.message });
    }
}

function rememberPending(handle, buffer, requested, overlapped) {
    if (!shouldCapture(handle) || overlapped.isNull() || readCommInfo(handle) === null) {
        return;
    }
    pendingReads.set(overlapped.toString(), {
        handle: handle,
        buffer: buffer,
        requested: requested,
        overlapped: overlapped,
        created: Date.now()
    });
}

function completePending(overlapped, transferred) {
    const key = overlapped.toString();
    const pending = pendingReads.get(key);
    if (!pending) {
        return;
    }
    pendingReads.delete(key);
    emitSerial('rx', pending.handle, pending.buffer, Math.min(transferred, pending.requested));
}

function hookCreateFile(name, wide) {
    const address = Module.findGlobalExportByName(name);
    if (address === null) {
        return;
    }
    Interceptor.attach(address, {
        onEnter(args) {
            try {
                this.path = wide ? args[0].readUtf16String() : args[0].readAnsiString();
            } catch (_) {
                this.path = '';
            }
        },
        onLeave(retval) {
            if (!isValidHandle(retval) || !this.path) {
                return;
            }
            if (/^(\\\\\.\\)?COM\d+:?$/i.test(this.path)) {
                namedHandles.set(handleKey(retval), this.path.replace(/^\\\\\.\\/, '').replace(/:$/, '').toUpperCase());
            }
        }
    });
}

hookCreateFile('CreateFileW', true);
hookCreateFile('CreateFileA', false);

Interceptor.attach(exportAddress('kernel32.dll', 'WriteFile'), {
    onEnter(args) {
        this.handle = args[0];
        this.buffer = args[1];
        this.requested = args[2].toUInt32();
        this.isSerial = readCommInfo(this.handle) !== null;
    },
    onLeave(retval) {
        if (!this.isSerial) {
            return;
        }
        const accepted = retval.toInt32() !== 0 || this.lastError === 997;
        if (accepted) {
            emitSerial('tx', this.handle, this.buffer, this.requested);
        }
    }
});

Interceptor.attach(exportAddress('kernel32.dll', 'ReadFile'), {
    onEnter(args) {
        this.handle = args[0];
        this.buffer = args[1];
        this.requested = args[2].toUInt32();
        this.bytesRead = args[3];
        this.overlapped = args[4];
        this.isSerial = readCommInfo(this.handle) !== null;
    },
    onLeave(retval) {
        if (!this.isSerial) {
            return;
        }
        if (retval.toInt32() !== 0) {
            let count = 0;
            if (!this.bytesRead.isNull()) {
                count = this.bytesRead.readU32();
            }
            emitSerial('rx', this.handle, this.buffer, Math.min(count, this.requested));
        } else if (this.lastError === 997 && !this.overlapped.isNull()) {
            rememberPending(this.handle, this.buffer, this.requested, this.overlapped);
        }
    }
});

const readFileExAddress = Module.findGlobalExportByName('ReadFileEx');
if (readFileExAddress !== null) {
    Interceptor.attach(readFileExAddress, {
        onEnter(args) {
            this.handle = args[0];
            this.buffer = args[1];
            this.requested = args[2].toUInt32();
            this.overlapped = args[3];
            this.isSerial = readCommInfo(this.handle) !== null;
        },
        onLeave(retval) {
            if (this.isSerial && retval.toInt32() !== 0) {
                rememberPending(this.handle, this.buffer, this.requested, this.overlapped);
            }
        }
    });
}

Interceptor.attach(exportAddress('kernel32.dll', 'GetOverlappedResult'), {
    onEnter(args) {
        this.overlapped = args[1];
        this.transferred = args[2];
    },
    onLeave(retval) {
        if (!probeActive && retval.toInt32() !== 0 && !this.transferred.isNull()) {
            completePending(this.overlapped, this.transferred.readU32());
        }
    }
});

const getOverlappedResultExAddress = Module.findGlobalExportByName('GetOverlappedResultEx');
if (getOverlappedResultExAddress !== null) {
    Interceptor.attach(getOverlappedResultExAddress, {
        onEnter(args) {
            this.overlapped = args[1];
            this.transferred = args[2];
        },
        onLeave(retval) {
            if (retval.toInt32() !== 0 && !this.transferred.isNull()) {
                completePending(this.overlapped, this.transferred.readU32());
            }
        }
    });
}

Interceptor.attach(exportAddress('kernel32.dll', 'CloseHandle'), {
    onEnter(args) {
        this.handle = args[0];
        this.key = handleKey(args[0]);
        this.endpoint = endpointFor(args[0]);
        this.wasMonitored = monitoredHandles.has(this.key) ||
            (!filterEnabled && readCommInfo(args[0]) !== null);
    },
    onLeave(retval) {
        if (retval.toInt32() !== 0) {
            if (this.wasMonitored) {
                send({
                    type: 'serial_closed',
                    endpoint: this.endpoint,
                    handle: this.key
                });
            }
            serialHandles.delete(this.key);
            nonSerialHandles.delete(this.key);
            namedHandles.delete(this.key);
            monitoredHandles.delete(this.key);
            for (const [pendingKey, pending] of pendingReads.entries()) {
                if (handleKey(pending.handle) === this.key) {
                    pendingReads.delete(pendingKey);
                }
            }
        }
    }
});

// Some applications consume overlapped results through an I/O completion port and
// never call GetOverlappedResult. A short non-blocking probe closes that gap.
setInterval(function () {
    const now = Date.now();
    for (const [key, pending] of pendingReads.entries()) {
        const transferred = Memory.alloc(4);
        let done = false;
        probeActive = true;
        try {
            done = GetOverlappedResult(pending.handle, pending.overlapped, transferred, false);
        } finally {
            probeActive = false;
        }
        if (done) {
            pendingReads.delete(key);
            emitSerial('rx', pending.handle, pending.buffer, Math.min(transferred.readU32(), pending.requested));
        } else if (now - pending.created > 120000) {
            pendingReads.delete(key);
        }
    }
}, 8);

rpc.exports = {
    setendpoints(mapping) {
        filterEnabled = true;
        monitoredHandles.clear();
        for (const key of Object.keys(mapping)) {
            const normalized = ptr(key).toString();
            monitoredHandles.add(normalized);
            namedHandles.set(normalized, String(mapping[key]));
        }
        return monitoredHandles.size;
    }
};

send({ type: 'diagnostic', message: '串口观察器已加载，等待目标进程读写数据。' });
