using System;
using System.Runtime.InteropServices;
using System.Threading;

internal static class SerialTarget
{
    private const uint GenericRead = 0x80000000;
    private const uint GenericWrite = 0x40000000;
    private const uint OpenExisting = 3;
    private static readonly IntPtr InvalidHandle = new IntPtr(-1);

    [StructLayout(LayoutKind.Sequential)]
    private struct ComStat
    {
        public uint Flags;
        public uint InQueue;
        public uint OutQueue;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr CreateFile(
        string name,
        uint desiredAccess,
        uint shareMode,
        IntPtr securityAttributes,
        uint creationDisposition,
        uint flagsAndAttributes,
        IntPtr templateFile);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool ReadFile(
        IntPtr handle,
        byte[] buffer,
        uint bytesToRead,
        out uint bytesRead,
        IntPtr overlapped);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool WriteFile(
        IntPtr handle,
        byte[] buffer,
        uint bytesToWrite,
        out uint bytesWritten,
        IntPtr overlapped);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool ClearCommError(
        IntPtr handle,
        out uint errors,
        out ComStat stat);

    [DllImport("kernel32.dll")]
    private static extern bool CloseHandle(IntPtr handle);

    public static int Main()
    {
        IntPtr port = CreateFile(
            @"\\.\COM1",
            GenericRead | GenericWrite,
            0,
            IntPtr.Zero,
            OpenExisting,
            0,
            IntPtr.Zero);
        if (port == InvalidHandle)
        {
            Console.Error.WriteLine("Unable to open COM1: " + Marshal.GetLastWin32Error());
            return 2;
        }

        try
        {
            for (int index = 0; index < 120; index++)
            {
                byte[] outgoing = { 0xA5, 0x5A, (byte)index, 0x0D };
                uint written;
                WriteFile(port, outgoing, (uint)outgoing.Length, out written, IntPtr.Zero);

                uint errors;
                ComStat stat;
                if (ClearCommError(port, out errors, out stat) && stat.InQueue > 0)
                {
                    byte[] incoming = new byte[Math.Min(stat.InQueue, 256)];
                    uint read;
                    ReadFile(port, incoming, (uint)incoming.Length, out read, IntPtr.Zero);
                }
                Thread.Sleep(60);
            }
        }
        finally
        {
            CloseHandle(port);
        }
        return 0;
    }
}
