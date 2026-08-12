// narrate — turn the spoken commentary on a screen recording into a timestamped
// transcript.
//
// Claude cannot hear a video. This transcribes it on-device with the macOS 26
// Speech framework and prints one line per phrase, stamped with the second it
// was said — so a transcript line can be lined up against the frame `framegrab`
// pulled at the same moment. Explaining a flow out loud while recording it then
// works exactly the way it would with a person watching over your shoulder.
//
// On-device. Nothing is uploaded, and there is no install: the language model
// is fetched once by the OS on first use.
//
//   swift tools/narrate.swift <video-or-audio> [locale=en-US]
//   swift tools/narrate.swift --locales          # what languages are available
//
// Video files have their audio track exported to a temporary m4a first, because
// AVAudioFile will not read a movie container directly.

import AVFoundation
import Foundation
import Speech

let args = CommandLine.arguments

func fail(_ message: String) -> Never {
    FileHandle.standardError.write("\(message)\n".data(using: .utf8)!)
    exit(1)
}

let semaphore = DispatchSemaphore(value: 0)
var exitCode: Int32 = 0

Task {
    defer { semaphore.signal() }

    if args.count > 1, args[1] == "--locales" {
        let installed = await Set(SpeechTranscriber.installedLocales.map { $0.identifier(.bcp47) })
        for locale in await SpeechTranscriber.supportedLocales.sorted(by: {
            $0.identifier < $1.identifier
        }) {
            let tag = locale.identifier(.bcp47)
            print("\(installed.contains(tag) ? "✓" : " ") \(tag)")
        }
        return
    }

    guard args.count >= 2 else {
        FileHandle.standardError.write(
            "usage: narrate <video-or-audio> [locale=en-US]   |   narrate --locales\n".data(
                using: .utf8)!)
        exitCode = 2
        return
    }

    let inputURL = URL(fileURLWithPath: args[1])
    let localeTag = args.count > 2 ? args[2] : "en-US"

    do {
        // AVAudioFile reads audio containers only, so a movie is bounced to m4a
        // first. Cheap: it is a passthrough of the existing audio track.
        var audioURL = inputURL
        var temporary: URL?
        if (try? AVAudioFile(forReading: inputURL)) == nil {
            let asset = AVURLAsset(url: inputURL)
            guard try await !asset.loadTracks(withMediaType: .audio).isEmpty else {
                fail("no audio track in \(inputURL.lastPathComponent) — was the recording muted?")
            }
            let out = FileManager.default.temporaryDirectory
                .appendingPathComponent("narrate-\(UUID().uuidString).m4a")
            guard
                let export = AVAssetExportSession(asset: asset, presetName: AVAssetExportPresetAppleM4A)
            else { fail("could not open an export session") }
            try await export.export(to: out, as: .m4a)
            audioURL = out
            temporary = out
        }
        defer { if let t = temporary { try? FileManager.default.removeItem(at: t) } }

        let locale = Locale(identifier: localeTag)
        let transcriber = SpeechTranscriber(
            locale: locale, preset: .timeIndexedProgressiveTranscription)

        if let request = try await AssetInventory.assetInstallationRequest(supporting: [transcriber]) {
            FileHandle.standardError.write(
                "fetching the \(localeTag) speech model, once only…\n".data(using: .utf8)!)
            try await request.downloadAndInstall()
        }

        let analyzer = SpeechAnalyzer(modules: [transcriber])
        let file = try AVAudioFile(forReading: audioURL)

        let reader = Task {
            for try await result in transcriber.results where result.isFinal {
                let seconds = CMTimeGetSeconds(result.range.start)
                let text = String(result.text.characters).trimmingCharacters(in: .whitespaces)
                if text.isEmpty { continue }
                print(
                    String(
                        format: "[%02d:%02d] %@", Int(seconds) / 60, Int(seconds) % 60, text))
            }
        }

        _ = try await analyzer.analyzeSequence(from: file)
        try await analyzer.finalizeAndFinishThroughEndOfInput()
        try await reader.value
    } catch {
        FileHandle.standardError.write("failed: \(error)\n".data(using: .utf8)!)
        exitCode = 1
    }
}

semaphore.wait()
exit(exitCode)
