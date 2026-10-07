import { deflateRawSync } from 'node:zlib'

export interface ZipEntry {
  name: string
  data: Buffer
}

/**
 * Creates a standard PKZip (.zip) buffer from an array of files.
 * Uses deflate compression via Node's built-in zlib with standard PKZip 2.0 headers.
 */
export function createZipBuffer(entries: ZipEntry[]): Buffer {
  const localHeaders: Buffer[] = []
  const centralHeaders: Buffer[] = []
  let offset = 0

  for (const entry of entries) {
    const nameBuf = Buffer.from(entry.name, 'utf-8')
    const uncompressedData = entry.data
    const compressedData = deflateRawSync(uncompressedData)
    const crc = crc32(uncompressedData)

    // Local file header (30 bytes + name length)
    const localHeader = Buffer.alloc(30 + nameBuf.length)
    localHeader.writeUInt32LE(0x04034b50, 0) // signature
    localHeader.writeUInt16LE(20, 4) // version needed (2.0)
    localHeader.writeUInt16LE(0x0800, 6) // flags (UTF-8)
    localHeader.writeUInt16LE(8, 8) // compression method (deflate)
    localHeader.writeUInt16LE(0, 10) // mod time
    localHeader.writeUInt16LE(0, 12) // mod date
    localHeader.writeUInt32LE(crc, 14) // crc32
    localHeader.writeUInt32LE(compressedData.length, 18) // compressed size
    localHeader.writeUInt32LE(uncompressedData.length, 22) // uncompressed size
    localHeader.writeUInt16LE(nameBuf.length, 26) // filename length
    localHeader.writeUInt16LE(0, 28) // extra field length
    nameBuf.copy(localHeader, 30)

    localHeaders.push(localHeader, compressedData)

    // Central directory header (46 bytes + name length)
    const centralHeader = Buffer.alloc(46 + nameBuf.length)
    centralHeader.writeUInt32LE(0x02014b50, 0) // signature
    centralHeader.writeUInt16LE(20, 4) // version made by
    centralHeader.writeUInt16LE(20, 6) // version needed
    centralHeader.writeUInt16LE(0x0800, 8) // flags
    centralHeader.writeUInt16LE(8, 10) // compression method
    centralHeader.writeUInt16LE(0, 12) // mod time
    centralHeader.writeUInt16LE(0, 14) // mod date
    centralHeader.writeUInt32LE(crc, 16) // crc32
    centralHeader.writeUInt32LE(compressedData.length, 20) // compressed size
    centralHeader.writeUInt32LE(uncompressedData.length, 24) // uncompressed size
    centralHeader.writeUInt16LE(nameBuf.length, 28) // filename length
    centralHeader.writeUInt16LE(0, 30) // extra field length
    centralHeader.writeUInt16LE(0, 32) // file comment length
    centralHeader.writeUInt16LE(0, 34) // disk number start
    centralHeader.writeUInt16LE(0, 36) // internal file attributes
    centralHeader.writeUInt32LE(0, 38) // external file attributes
    centralHeader.writeUInt32LE(offset, 42) // relative offset of local header
    nameBuf.copy(centralHeader, 46)

    centralHeaders.push(centralHeader)
    offset += localHeader.length + compressedData.length
  }

  const centralDirOffset = offset
  const centralDirBuf = Buffer.concat(centralHeaders)
  const centralDirSize = centralDirBuf.length

  // End of central directory record (22 bytes)
  const eocd = Buffer.alloc(22)
  eocd.writeUInt32LE(0x06054b50, 0) // signature
  eocd.writeUInt16LE(0, 4) // number of this disk
  eocd.writeUInt16LE(0, 6) // disk with start of central directory
  eocd.writeUInt16LE(entries.length, 8) // total entries on this disk
  eocd.writeUInt16LE(entries.length, 10) // total entries in central directory
  eocd.writeUInt32LE(centralDirSize, 12) // size of central directory
  eocd.writeUInt32LE(centralDirOffset, 16) // offset of start of central directory
  eocd.writeUInt16LE(0, 20) // comment length

  return Buffer.concat([...localHeaders, centralDirBuf, eocd])
}

// CRC32 table & calculator
const CRC_TABLE = new Uint32Array(256)
for (let i = 0; i < 256; i++) {
  let c = i
  for (let k = 0; k < 8; k++) {
    c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
  }
  CRC_TABLE[i] = c
}

function crc32(buf: Buffer): number {
  let crc = 0xffffffff
  for (let i = 0; i < buf.length; i++) {
    crc = CRC_TABLE[(crc ^ buf[i]) & 0xff] ^ (crc >>> 8)
  }
  return (crc ^ 0xffffffff) >>> 0
}
