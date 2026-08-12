// framegrab — pull the distinct screens out of a screen recording.
//
// Claude cannot watch a video, but it reads images natively. This walks a
// recording at a fixed interval, throws away frames that look the same as the
// last one it kept, and writes what is left as numbered PNGs. A three-minute
// UI walkthrough comes out as twenty or thirty actual screens instead of two
// hundred near-duplicates.
//
// Pure AVFoundation + CoreGraphics: no ffmpeg, no brew, nothing to install.
//
//   swift tools/framegrab.swift <video> <outdir> [everySec=1.5] [maxWidth=900] [diff=6]
//
// `diff` is the sensitivity, 0–255. Lower keeps more frames. 6 is tuned for UI
// recordings, where a real screen change moves a lot of pixels and a fade or a
// cursor twitch moves very few.

import AVFoundation
import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

let args = CommandLine.arguments
guard args.count >= 3 else {
    FileHandle.standardError.write(
        "usage: framegrab <video> <outdir> [everySec=1.5] [maxWidth=900] [diff=6]\n".data(using: .utf8)!)
    exit(2)
}

let inputURL = URL(fileURLWithPath: args[1])
let outDir = URL(fileURLWithPath: args[2])
let everySec = args.count > 3 ? (Double(args[3]) ?? 1.5) : 1.5
let maxWidth = args.count > 4 ? (Int(args[4]) ?? 900) : 900
let diffThreshold = args.count > 5 ? (Double(args[5]) ?? 6) : 6

/// A 16×16 grey thumbprint. Cheap, and enough to tell one screen from another.
func signature(_ image: CGImage) -> [UInt8] {
    let n = 16
    var bytes = [UInt8](repeating: 0, count: n * n)
    guard
        let ctx = CGContext(
            data: &bytes, width: n, height: n, bitsPerComponent: 8, bytesPerRow: n,
            space: CGColorSpaceCreateDeviceGray(), bitmapInfo: CGImageAlphaInfo.none.rawValue)
    else { return bytes }
    ctx.draw(image, in: CGRect(x: 0, y: 0, width: n, height: n))
    return bytes
}

func meanDifference(_ a: [UInt8], _ b: [UInt8]) -> Double {
    guard a.count == b.count, !a.isEmpty else { return 255 }
    var total = 0
    for i in 0..<a.count { total += abs(Int(a[i]) - Int(b[i])) }
    return Double(total) / Double(a.count)
}

func downscale(_ image: CGImage, to width: Int) -> CGImage {
    guard image.width > width else { return image }
    let height = Int(Double(image.height) * Double(width) / Double(image.width))
    guard
        let ctx = CGContext(
            data: nil, width: width, height: height, bitsPerComponent: 8, bytesPerRow: 0,
            space: CGColorSpace(name: CGColorSpace.sRGB)!,
            bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)
    else { return image }
    ctx.interpolationQuality = .high
    ctx.draw(image, in: CGRect(x: 0, y: 0, width: width, height: height))
    return ctx.makeImage() ?? image
}

func writePNG(_ image: CGImage, to url: URL) -> Bool {
    guard
        let dest = CGImageDestinationCreateWithURL(
            url as CFURL, UTType.png.identifier as CFString, 1, nil)
    else { return false }
    CGImageDestinationAddImage(dest, image, nil)
    return CGImageDestinationFinalize(dest)
}

let semaphore = DispatchSemaphore(value: 0)
var exitCode: Int32 = 0

Task {
    defer { semaphore.signal() }
    do {
        try FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)

        let asset = AVURLAsset(url: inputURL)
        let duration = try await CMTimeGetSeconds(asset.load(.duration))
        guard duration.isFinite, duration > 0 else {
            FileHandle.standardError.write("no readable video track\n".data(using: .utf8)!)
            exitCode = 1
            return
        }

        let generator = AVAssetImageGenerator(asset: asset)
        generator.appliesPreferredTrackTransform = true
        // Exact frames: a tolerant generator hands back the same keyframe over
        // and over, which the deduplicator would then correctly discard.
        generator.requestedTimeToleranceBefore = .zero
        generator.requestedTimeToleranceAfter = .zero

        var lastSignature: [UInt8] = []
        var kept = 0
        var examined = 0
        var timestamp = 0.0

        print("duration \(String(format: "%.1f", duration))s · sampling every \(everySec)s")

        while timestamp < duration {
            let time = CMTime(seconds: timestamp, preferredTimescale: 600)
            if let frame = try? await generator.image(at: time).image {
                examined += 1
                let sig = signature(frame)
                let delta = lastSignature.isEmpty ? 255 : meanDifference(sig, lastSignature)
                if delta >= diffThreshold {
                    lastSignature = sig
                    kept += 1
                    let name = String(
                        format: "%03d_%06.1fs.png", kept, timestamp)
                    let url = outDir.appendingPathComponent(name)
                    if writePNG(downscale(frame, to: maxWidth), to: url) {
                        print("  \(name)   change \(String(format: "%.1f", delta))")
                    }
                }
            }
            timestamp += everySec
        }

        print("\(kept) distinct screens kept from \(examined) sampled")
    } catch {
        FileHandle.standardError.write("failed: \(error)\n".data(using: .utf8)!)
        exitCode = 1
    }
}

semaphore.wait()
exit(exitCode)
