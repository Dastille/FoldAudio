"""ShockDAQ on a second public bearing dataset: Paderborn University KAt
Bearing DataCenter, vibration channel at 64 kHz (NOTES #8g, 2026-10-23).

Why: CWRU (``realdata.py``) only goes up to 48 kHz and showed that sample rate
decides whether fold can recover an overload at all (7.5–9.8 dB at 48 kHz,
none at 12 kHz). Paderborn records the bearing-housing accelerometer at 64 kHz,
so it tests that finding on a second test rig, a second sensor chain and a
higher rate. The scoring chain is exactly ``realdata.eval_record``.

Named ASSUMPTIONS (same as the CWRU study unless stated):

1. The recorded ``vibration_1`` channel is treated as the true sensor output.
   The dataset does not state its unit in the .mat file, so numbers are
   reported as ratios (Δ/peak, λ/peak, dB) and the raw unit is "dataset units".
2. Overload is applied in software (λ = r · peak); the KAt rig did not overload.
3. Ideal fold, blind recovery (zero-mean prior); the original is used only for
   scoring. "Recovered" = max |x̂ − x| ≤ 1e-6 · peak.
4. "64→16k" rows are plain 4:1 subsampling (no anti-alias filter), as in CWRU.
5. Source files: the KAt archives as mirrored on Zenodo (record 15845309,
   CC BY 4.0, MD5 listed by Zenodo). Only the needed .mat members are extracted
   (needs the ``unar`` command-line tool) and each is pinned by SHA-256. Nothing
   is redistributed in this repository.
6. CPU only.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import urllib.request
from dataclasses import asdict
from pathlib import Path

import numpy as np

from .foldaudio import max_sample_jump
from .realdata import RealCell, eval_record, headroom_db, kurtosis, summarize

SR = 64_000
ZENODO_URL = "https://zenodo.org/api/records/15845309/files/{bearing}.rar/content"

#: bearing code → (label, MD5 of the .rar as listed by Zenodo record 15845309)
BEARINGS: dict[str, tuple[str, str]] = {
    "K001": ("healthy", "af6dc58283d356cd438e7738a2d525b8"),
    "KA04": ("outer ring, fatigue pitting", "f87503ed69a624ba6e1d9e573e6c09fb"),
    "KI04": ("inner ring, fatigue pitting", "a5a634fcdcb33a8501e7411d30441c6d"),
}

#: operating conditions (speed / torque / radial force codes), measurement _1
CONDITIONS = ("N15_M07_F10", "N09_M07_F10", "N15_M01_F10", "N15_M07_F04")

#: member name → SHA-256 of the extracted .mat (filled 2026-10-23)
MAT_SHA256: dict[str, str] = {
    "K001/N09_M07_F10_K001_1.mat": "c55f4c6a5d6d9a83d18d24dce4f164ffc85721e4e358df1c1ac9886583c2269f",
    "K001/N15_M01_F10_K001_1.mat": "84ff03769c3efa9cd2c3e0cbeefa60ed6bcec3436efa804637788a638b5f23f3",
    "K001/N15_M07_F04_K001_1.mat": "4790406e566cd6ed93241bc0a1e51ea7b9603c38a712a93d2946140dfa581458",
    "K001/N15_M07_F10_K001_1.mat": "e1a971e93991e5f8bbfdcacde5a0fec895a4248f8232d52b59ff85d034c9c00d",
    "KA04/N09_M07_F10_KA04_1.mat": "7db59955c834c4f74e8360bc873a4adc27beb569cf4406ba857777b1f986f138",
    "KA04/N15_M01_F10_KA04_1.mat": "060dc5acbcab35a2aaad7d19be4b771e993a29f5b927d66bec96d23a972fd040",
    "KA04/N15_M07_F04_KA04_1.mat": "46f3a5e8984ed72eca6b0824764c8c608132918ba6185002a59433c35904ae3e",
    "KA04/N15_M07_F10_KA04_1.mat": "c1caff884401a8476d3e8f42fb6efcd57c721888706af26cfeaeb2c3e99b35a5",
    "KI04/N09_M07_F10_KI04_1.mat": "fa5d43cd8ab8cec9cadb0b9356096231b9f2a1a925a2bf935b5d3bcb2eecdf5f",
    "KI04/N15_M01_F10_KI04_1.mat": "24cd3f08730e2ffe0117e77ef8eb14433b6131bddf6508d2ea50bae950f936b3",
    "KI04/N15_M07_F04_KI04_1.mat": "935c1b56751894110c6256fa3d06b0cc9e526417d0b7eee92abeaea1dce0617f",
    "KI04/N15_M07_F10_KI04_1.mat": "d77409dca95d03986b5957b73c2219f42f7bbfd8080ebbf6f5b9f11571476f9c",
    # held-out measurements _2.._5 (NOTES #8i), pinned 2026-10-26 before analysis
    "K001/N15_M07_F10_K001_2.mat": "9ed50c2cf9b280e65471ee9dde35b280b5deb43a6fc861fabd7935bd772f969a",
    "K001/N15_M07_F10_K001_3.mat": "721a04849ea72d90bcf623f80b2d6ca8126f3b13910f34319495af0554795549",
    "K001/N15_M07_F10_K001_4.mat": "d4ee7fef3b3f2b1f310324034ee22894a84163d7b078c63210f77ffa589f9dc0",
    "K001/N15_M07_F10_K001_5.mat": "f47c9c9de878ba24479b7f8c1cb48c813354ec71a57112d35b1d87986124fe55",
    "K001/N09_M07_F10_K001_2.mat": "353451b91afc757be1883b4af2ba36724d58534a24b310662be7cd93dba156bb",
    "K001/N09_M07_F10_K001_3.mat": "6c4d86af80479b864b57966669574a00b218370b1e75f75411bbc50599e60dd3",
    "K001/N09_M07_F10_K001_4.mat": "8396cebc4fe63ee49b4282ae6e4f6989ed5f9fdd65dcec9b89c13a6ff4ab201e",
    "K001/N09_M07_F10_K001_5.mat": "44c8d4df1c288ba321c10795122da1cacb37471302aa41183b131f655d90088d",
    "K001/N15_M01_F10_K001_2.mat": "a47179a2266ebb83132ccd844cc6b685cdfd5355c9d6fd53a13f1744d9e05304",
    "K001/N15_M01_F10_K001_3.mat": "2f385585e485962b0563651cae9c72c4ff178ceec5938950e0d87e2b754b9d94",
    "K001/N15_M01_F10_K001_4.mat": "12746ba1bf85716ac7ae5c8e182792b412de83d82bf8daa0aef3ccf1ada3ad32",
    "K001/N15_M01_F10_K001_5.mat": "19e5d6b775a3a810640adaef02354bced5f5dcb70f93b351f299ed92f1d96e91",
    "K001/N15_M07_F04_K001_2.mat": "b0eea67e384a64b4585273a81dc48fd6093c57a98e2e25966187b6c914e73b72",
    "K001/N15_M07_F04_K001_3.mat": "be5b0d6ec89ab7d6fbbe72a7600148fe5a11b489e3a9865c0717d82374418898",
    "K001/N15_M07_F04_K001_4.mat": "c83b69d9d725bb53ff59eff2f43c7a29316a01f6f449db29036c0a4edc0054c3",
    "K001/N15_M07_F04_K001_5.mat": "c9baa4c611ef25d37abd2ead35caf0f655cb9da111e915b187f1ccb2c1226501",
    "KA04/N15_M07_F10_KA04_2.mat": "22210c904d75338060e03859cab6c6c55c1f509ff250e266f178eb198b210017",
    "KA04/N15_M07_F10_KA04_3.mat": "6ae0d36410a6dd32ac307ab8ffae4d81b867b433b01ab24dcc1a12172dff2f31",
    "KA04/N15_M07_F10_KA04_4.mat": "700369d50867284ed9969d730354d4fe9e60b29d7e90e568359fcbee26615e07",
    "KA04/N15_M07_F10_KA04_5.mat": "c6dc56d18a2704193756e502b656ca21781b6ec983e4b36c5a2ef7c939d1cbfa",
    "KA04/N09_M07_F10_KA04_2.mat": "4e66934fe250625318364b3973468faedd555b66156f8d9212f5f14a2fd1f4a5",
    "KA04/N09_M07_F10_KA04_3.mat": "2e543cbd0d246ac0eff03b95f4d9e0e94a72c39000d70c93d6608239ab03d259",
    "KA04/N09_M07_F10_KA04_4.mat": "09426652f1cd315bc515fe78efda2b990c8c6b89bcf1e77db721bbfe638e5638",
    "KA04/N09_M07_F10_KA04_5.mat": "8bd04b23789c5f09a360c144784223f857c462ac7df113450061ecef66ebd9db",
    "KA04/N15_M01_F10_KA04_2.mat": "c0d941668d8f08ab37c3d2c248a43abbed2faea28b7823e1a3efeec29eb139dc",
    "KA04/N15_M01_F10_KA04_3.mat": "35c5de1a76b9016de9efda509006d91d9446e25765f6478a4d46914b4c8f4d98",
    "KA04/N15_M01_F10_KA04_4.mat": "51aeb6a22b9d40bf7ef5e42e71fd6b4034374cf51f0b782ecb440dbfbbca81db",
    "KA04/N15_M01_F10_KA04_5.mat": "e2b542b321ecfb15233795903eae2b45bc2d72c42d7cb5066952213e77f87ac9",
    "KA04/N15_M07_F04_KA04_2.mat": "e9186aefeb54f3ed36e59160b0cd5f38d63c6516ebd412948e92b924a0fcdc52",
    "KA04/N15_M07_F04_KA04_3.mat": "fe7426500684250bf32bce968b79d0e254bf3b56792745790386e7f3ccef04e6",
    "KA04/N15_M07_F04_KA04_4.mat": "fbf129ea0e125092f5e82c853840e63876f2e0a4368f5088267c4efbceba458b",
    "KA04/N15_M07_F04_KA04_5.mat": "7d3cc4032c59523404faf152596cd6b9c6f97b93b88938f49f617ab4b5b9abc6",
    "KI04/N15_M07_F10_KI04_2.mat": "21e8db6824fb887c13ac5fefcd678d81b70c51734d6fc9a24fb580a9acf3d2dc",
    "KI04/N15_M07_F10_KI04_3.mat": "160e9630ad5c2d9c8378eed1ee5d596177d85d31aad1bbb3f396b8305aadb5bd",
    "KI04/N15_M07_F10_KI04_4.mat": "6c8cf4dc8f8df64561c9ad653f6d2bf0c48fd9d1a534276a22ebc13fa2d5b27d",
    "KI04/N15_M07_F10_KI04_5.mat": "65844dfbaf87208e490960fb0f7ae9c8f69dc6d85a171becf76abfa5629213bb",
    "KI04/N09_M07_F10_KI04_2.mat": "c993511853ff0a4326896586e0d21e06e0f3ad56be2c08f7a3e204a4e00ab9e9",
    "KI04/N09_M07_F10_KI04_3.mat": "dfb89ba32084c6563b11569c6413368e5cf24f907f9dc9711dcb5e11a20f75ca",
    "KI04/N09_M07_F10_KI04_4.mat": "3921cd85b2c14e36124fe83434ed742455d1ece94db4997e7af753888e96421a",
    "KI04/N09_M07_F10_KI04_5.mat": "bcb8337e6cac324c82712abf92d2a48184fc6bcbd07aaa99cee0423cfe99da00",
    "KI04/N15_M01_F10_KI04_2.mat": "12ba66b4a46a7e80edda7bf1488cd466b6d1f6e74764b98ea54cdcfc407e0293",
    "KI04/N15_M01_F10_KI04_3.mat": "925ed9eb060749da30e696e1b5e1fabf3504fc4c3aaf81803e6762c832672659",
    "KI04/N15_M01_F10_KI04_4.mat": "bf5097d71828555e329fc66fe4f93742154ac50c50c7efa296207a79ff399631",
    "KI04/N15_M01_F10_KI04_5.mat": "12b7c250d7ea6581701d2222610a0ddd12af9aa79ab93be96c97e994924c7149",
    "KI04/N15_M07_F04_KI04_2.mat": "4c3bb2a4c26da6655fdc75678b3d744058b05aaf19ee96c49a301971f5a5fd0d",
    "KI04/N15_M07_F04_KI04_3.mat": "bc4020a6282482aad661690b204ad133dcee45d6b6c36073a26beb94050ddb28",
    "KI04/N15_M07_F04_KI04_4.mat": "cdbfa5ea85ab3befa445d83e8787635b796da9fe6b6b7ad9f43fcefb0d0ae39c",
    "KI04/N15_M07_F04_KI04_5.mat": "469c137ee402d25f97781110ff07338ca2f10191750fcdca82a7de2693dab6b0",
    # fresh measurements _6.._10 of K001/KI04 (NOTES #8k), pinned 2026-10-28 before analysis
    "K001/N15_M07_F10_K001_6.mat": "725dcc9f7d78a07aeb9f221e34a35d144911cdab561da1828a2f0d403826dde5",
    "K001/N15_M07_F10_K001_7.mat": "50db4e44b1ac337053a8ba45d7bfde75388eb6950ed9829f93af30980344a72e",
    "K001/N15_M07_F10_K001_8.mat": "dbeed0fc3bc2a7430cab577922d144e42070108e361e7cb2cb528c70f3ff447f",
    "K001/N15_M07_F10_K001_9.mat": "a4d412efe4c57563e79ddfe99d2d15b18d53c3b08af0c6fcb28c086a9d3ecbbd",
    "K001/N15_M07_F10_K001_10.mat": "48658a7101a3692896fb7b6c21d26ced9c43e7acae44ef86b68134f3ac653818",
    "K001/N09_M07_F10_K001_6.mat": "b92664766ba37c9bde910207ad65ce8bc08ee3d3978133fe75793e69563d08e6",
    "K001/N09_M07_F10_K001_7.mat": "780298e958182f42edf581af01184208e8069a56e32e46ec0d3ceb621b772760",
    "K001/N09_M07_F10_K001_8.mat": "477499b31da6fa82a8a7f9a9a0af6365be4dbf2c0b60c6a6293549eb56f72cb9",
    "K001/N09_M07_F10_K001_9.mat": "d805b827dc2fad6168a30caf68d25d2ee93b9cfb78fc4b38c95184f4db11dc0d",
    "K001/N09_M07_F10_K001_10.mat": "048fca3a6d4942eeb42e16108801af0ee88486951a10a24458f59cf7c0865c3b",
    "K001/N15_M01_F10_K001_6.mat": "81c8b9b5cd1dc659c34ee10aff3bd997ee316202a1fd1c076dcd105c79895c1a",
    "K001/N15_M01_F10_K001_7.mat": "8abfac8489a9747914ed5cc30fa7c1c5eba2625815772385a9133c83a49e8c80",
    "K001/N15_M01_F10_K001_8.mat": "f9766972b8b0bb1d6aa191b616e708f468d37205cc9c7e8e77c42388f7f65042",
    "K001/N15_M01_F10_K001_9.mat": "3f37ff5bed1f4986fa55ee4ae16d2dfb6e6dfd281fb3f09cd5d983e6749c9765",
    "K001/N15_M01_F10_K001_10.mat": "a5c50eed5d13f968f61411933d9cc682523b6950796d52a40d9125a22e6027bb",
    "K001/N15_M07_F04_K001_6.mat": "f4e905384eb6fc1346154dae7fea5222a80dc8c93a80e71eccb190331b9becec",
    "K001/N15_M07_F04_K001_7.mat": "28ece81fc88419f91a58fd1ebb59679c5f27ba0316540c1cc06074d0cc9ed1f3",
    "K001/N15_M07_F04_K001_8.mat": "223481b7138be4e0c4379292d1b2892631193fbc374f26c5f9ecdf00c7bf7ac9",
    "K001/N15_M07_F04_K001_9.mat": "1e0100be9afb33b971959d80ad6ff4df303745b3fdce3f4904b60a53d438e682",
    "K001/N15_M07_F04_K001_10.mat": "7763d99131bd4651094f37820c754483be3124c6ee754ac95e3645712143899b",
    "KI04/N15_M07_F10_KI04_6.mat": "02710f54333f645b2ad1c89cf446b01d8ae3008bdd879552d475ef16dff6c100",
    "KI04/N15_M07_F10_KI04_7.mat": "bd8d95f004bed7212fc54648edf53d146ab06a1569deeb9719d041b0b86db1e0",
    "KI04/N15_M07_F10_KI04_8.mat": "2b8c81e7a2a0648880625b253bc55f8afb47ec38f3e6e2f79ef6163e128a1eef",
    "KI04/N15_M07_F10_KI04_9.mat": "a469993c92fe27379c16ea2db3587b931e8076a805a83296f5b9cf5be1e706fe",
    "KI04/N15_M07_F10_KI04_10.mat": "f10c64e27ebde65f8a466c2b5f4b4b353931136e32f6f299d6c43f3eae45e5a3",
    "KI04/N09_M07_F10_KI04_6.mat": "fa3d3299f1f2c2d7143f528a2d55ede6d110d5fadda30dd5957e2aec7fa32775",
    "KI04/N09_M07_F10_KI04_7.mat": "028bb40a85d1cc4907b39b9e95c04da530ef69afd35ddaecc87e46a14a074b22",
    "KI04/N09_M07_F10_KI04_8.mat": "9516c6e5ec95889580575215f60d1a9c198a9d2b3f57f917fb22b7490facac1b",
    "KI04/N09_M07_F10_KI04_9.mat": "3522d004c1488cce989ec8c983175182f86bbd3e258fd248aa6852a554c65552",
    "KI04/N09_M07_F10_KI04_10.mat": "2c4049c485ed4987d711ef4efab4a66dbce09c9b476fceec3b940d6e1da58b77",
    "KI04/N15_M01_F10_KI04_6.mat": "01d12f7aa1f4117a766be6ffa74d4be18f4a4ae8deac5a38c0ca10a5059072b7",
    "KI04/N15_M01_F10_KI04_7.mat": "de4a397b0924cb97feb897d62799b0110aa25dbf1cc0134a2987a37e665588a5",
    "KI04/N15_M01_F10_KI04_8.mat": "8c76ebe6ab7311e685d39a4bcd598e1400b00567945ea1c263ae7adc5bd65e5f",
    "KI04/N15_M01_F10_KI04_9.mat": "0a791ee6d1dc4364e72087fdbfd50083ecfbf1797765699a55cd7aed2be310ca",
    "KI04/N15_M01_F10_KI04_10.mat": "c308fa34dbdef64b2e5ca28ee27c5866237276ebb56af84955b56a201b61160b",
    "KI04/N15_M07_F04_KI04_6.mat": "0be0837ddee491b33a27e6deb71cb55a8f180506c9621cd40aa0040aabb72bf6",
    "KI04/N15_M07_F04_KI04_7.mat": "7b7c2a1db6032baacb0ab82f9418369cb235695b7444fcea53ee2d1b45358edf",
    "KI04/N15_M07_F04_KI04_8.mat": "f23250c7a4849046cb12e00b2da65694196e0eeb6840c1bf49b0f39ba5349192",
    "KI04/N15_M07_F04_KI04_9.mat": "fd768b256d1f40b0862ed3bbe9b2aa8112fe0042c88da8dce03daa57c7688f38",
    "KI04/N15_M07_F04_KI04_10.mat": "8508d0d0645e098394ec96b8f32593c521c59373517ca7ec8f095eb80070288b",
    # fresh KA04 (spike-free control) measurements _6.._10 (NOTES #8k item c), pinned 2026-10-29 before analysis
    "KA04/N15_M07_F10_KA04_6.mat": "50437d1d4d20b95019dffbe8cbfd9e2e0299a09811fdab1820c515d52439ffd5",
    "KA04/N09_M07_F10_KA04_6.mat": "089cb63671075e9fe7fa0e8d8f0fa61aef22a6f90301825672e5eacc62107467",
    "KA04/N15_M01_F10_KA04_6.mat": "3dc2c37b145360898d8a6a2541bb80ca116fffb9e531e5601c9264479cbe4e4f",
    "KA04/N15_M07_F04_KA04_6.mat": "ce84c766f9441a1fe31c3029ef9108e86993adda5b80237380c0723f372e0c51",
    "KA04/N15_M07_F10_KA04_7.mat": "6b44db883db5d95330f84edf66fbda8118e4a69080b7efd3d35bd95912e6e8e1",
    "KA04/N09_M07_F10_KA04_7.mat": "fd69ac9778ede7a592280b74addc0daf3d4389e9cf70b6d5234bc1000d46ffb8",
    "KA04/N15_M01_F10_KA04_7.mat": "74162e7f1fc9def576f6be6e6ace82c1a9de2d84ba2bf810cdfaeba50c0d2f95",
    "KA04/N15_M07_F04_KA04_7.mat": "f2ce40b216023b2ab67fd1e07846df11ee815864b73a8cae1cd5181e97429e78",
    "KA04/N15_M07_F10_KA04_8.mat": "ae13d0c51a5414e42f6d7a01b07f565da3b5328c86d9503ab6e389d55d0ca8ed",
    "KA04/N09_M07_F10_KA04_8.mat": "356bb61c4daa97abff5fe9cde729a001c954bfba29191c2b1e3de9ad092c5e72",
    "KA04/N15_M01_F10_KA04_8.mat": "5586b2998e1b38c02d6f1b7a87b8687d724d63d14a97104f794a1007e7d4c71a",
    "KA04/N15_M07_F04_KA04_8.mat": "173c107adbbf8f027c1d56f8de65ee1843f3a100b92e05877c5ad552a1e7f5fc",
    "KA04/N15_M07_F10_KA04_9.mat": "ee8f829093443313da6387955d6a8f70588c8fef2862b336e792876e1a32a837",
    "KA04/N09_M07_F10_KA04_9.mat": "13eee14a0a063e74575294e13906bce1eac415d250430285bc54eb413b72bb37",
    "KA04/N15_M01_F10_KA04_9.mat": "47079f51fbc2a1a01dc0b12e33e032594df115c969838551cd146ed5348e2e0c",
    "KA04/N15_M07_F04_KA04_9.mat": "3d9f13abd9be412f4775b50fb481cb6cbff0d70ba284b8d52cfe292883530b98",
    "KA04/N15_M07_F10_KA04_10.mat": "f08980bb636df4a470bd426e49ed7fb79520cd20621afdb54713485df8088699",
    "KA04/N09_M07_F10_KA04_10.mat": "289744a10c76513aeaaf1ae7eb5156cfc6ae935e7cadc955f7a07ca6ef279f13",
    "KA04/N15_M01_F10_KA04_10.mat": "1588ff7ef3c852798ec068f8e652d837bb09affdf1940002e544cccbdffd1cb6",
    "KA04/N15_M07_F04_KA04_10.mat": "a84964dcf0376736927ce4a18a7d6e6467e8a46b2a666cca65ceab8b2b0b3162",
}

#: Environment variable that overrides the Paderborn cache directory.
CACHE_ENV = "FOLDCRYPT_PADERBORN_CACHE"


def default_cache() -> Path:
    """``$FOLDCRYPT_PADERBORN_CACHE`` if set, else ``~/.cache/foldcrypt/paderborn``."""
    env = os.environ.get(CACHE_ENV, "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".cache" / "foldcrypt" / "paderborn"


#: held-out measurement numbers used by the 2026-10-26 confirmation (NOTES #8i)
HELDOUT_MEASUREMENTS = (2, 3, 4, 5)

#: fresh measurement numbers for the 2026-10-28 phase confirmation (NOTES #8k)
CONFIRM_MEASUREMENTS = (6, 7, 8, 9, 10)


def member(bearing: str, condition: str, meas: int = 1) -> str:
    """Archive member path, e.g. ``K001/N15_M07_F10_K001_1.mat``."""
    return f"{bearing}/{condition}_{bearing}_{meas}.mat"


def _digest(path: Path, algo: str) -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fetch_rar(bearing: str, cache: Path) -> Path:
    _label, md5 = BEARINGS[bearing]
    rar = cache / "rar" / f"{bearing}.rar"
    if rar.exists() and _digest(rar, "md5") == md5:
        return rar
    rar.parent.mkdir(parents=True, exist_ok=True)
    tmp = rar.with_suffix(".part")
    urllib.request.urlretrieve(ZENODO_URL.format(bearing=bearing), tmp)
    got = _digest(tmp, "md5")
    if got != md5:
        raise OSError(f"{bearing}.rar: MD5 mismatch (got {got}, want {md5})")
    tmp.replace(rar)
    return rar


def fetch(
    bearing: str,
    condition: str,
    cache: Path | str | None = None,
    *,
    download: bool = True,
    meas: int = 1,
) -> Path:
    """Checksum-verified local copy of one Paderborn measurement (.mat).

    ``meas`` selects the measurement number within the operating condition
    (1 for the 2026-10-23 sweep; 2–5 for the held-out confirmation)."""
    cache = Path(cache) if cache else default_cache()
    name = member(bearing, condition, meas)
    path = cache / name
    want = MAT_SHA256.get(name)
    if path.exists() and want is not None and _digest(path, "sha256") == want:
        return path
    if not download:
        raise FileNotFoundError(f"{path} missing or bad checksum")
    if shutil.which("unar") is None:
        raise OSError("extracting the Paderborn .rar archives needs the 'unar' tool")
    rar = _fetch_rar(bearing, cache)
    subprocess.run(
        ["unar", "-q", "-f", "-o", str(cache), str(rar), name],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    got = _digest(path, "sha256")
    if want is not None and got != want:
        raise OSError(f"{name}: SHA-256 mismatch (got {got})")
    return path


def load_vibration(path: Path | str) -> np.ndarray:
    """The ``vibration_1`` channel (64 kHz) from a Paderborn .mat file."""
    try:
        from scipy.io import loadmat
    except ImportError as e:  # pragma: no cover - depends on environment
        raise ImportError(
            "reading .mat files needs scipy: pip install '.[real]'"
        ) from e
    m = loadmat(str(path))
    keys = [k for k in m if not k.startswith("__")]
    if len(keys) != 1:
        raise ValueError(f"{path}: expected one measurement struct, found {keys}")
    rec = m[keys[0]][0, 0]
    for ch in rec["Y"][0]:
        if str(np.ravel(ch["Name"])[0]) == "vibration_1":
            return np.ravel(ch["Data"]).astype(float)
    raise ValueError(f"{path}: no vibration_1 channel")


def isolated_spikes(x: np.ndarray, frac: float = 0.5) -> int:
    """Count single-sample spikes: samples where the step in and the step out
    both exceed ``frac`` · peak and have opposite signs (the signal jumps away
    and straight back). One such sample sets max|Δx| on its own, so it alone
    can remove fold headroom (recovery needs λ > max|Δx|)."""
    x = np.asarray(x, dtype=float)
    if len(x) < 3:
        return 0
    bar = frac * float(np.max(np.abs(x)))
    d_in, d_out = x[1:-1] - x[:-2], x[2:] - x[1:-1]
    hit = (np.abs(d_in) > bar) & (np.abs(d_out) > bar) & (d_in * d_out < 0)
    return int(np.count_nonzero(hit))


def record_row(name: str, label: str, v: np.ndarray, sr: int) -> dict:
    """Per-record summary: peak, largest step, headroom, kurtosis."""
    pk, dx = float(np.max(np.abs(v))), max_sample_jump(v)
    return {
        "record": name,
        "label": label,
        "sr": sr,
        "n": int(len(v)),
        "peak": pk,
        "max_dx": dx,
        "dx_over_peak": dx / pk,
        "headroom_db": headroom_db(pk, dx),
        "kurtosis": kurtosis(v),
        "isolated_spikes": isolated_spikes(v),
    }


def run_sweep(
    cache: Path | str | None = None, *, download: bool = True, decimate: bool = True
) -> dict:
    """All BEARINGS × CONDITIONS at 64 kHz (and 64→16k), scored by eval_record."""
    cells: list[RealCell] = []
    records = []
    for b, (label, _md5) in BEARINGS.items():
        for cond in CONDITIONS:
            x = load_vibration(fetch(b, cond, cache, download=download))
            variants = [(f"{b}/{cond}@64k", x, SR)]
            if decimate:
                variants.append((f"{b}/{cond}@64→16k", x[::4], SR // 4))
            for name, v, vsr in variants:
                records.append(record_row(name, label, v, vsr))
                cells.extend(eval_record(name, label, v, vsr))
    return {"records": records, "cells": cells, "summary": summarize(cells)}


def write_report(sweep: dict, path: Path | str) -> None:
    out = {
        "source": "Paderborn University KAt Bearing DataCenter via Zenodo 15845309 (CC BY 4.0), vibration_1, 64 kHz, dataset units",
        "assumptions": [
            "Recorded vibration_1 treated as true sensor output; λ = ratio·peak applied in software.",
            "Ideal modulo fold; blind recovery (zero-mean prior); original used only for scoring.",
            "recovered = max|x̂−x| ≤ 1e-6·peak; silent = not recovered and neither slip nor edge flag.",
            "64→16k rows = plain 4:1 subsampling (no anti-alias filter).",
        ],
        "prereg": "artifacts/paderborn/prereg-2026-10-23.md",
        "records": sweep["records"],
        "summary": sweep["summary"],
        "cells": [asdict(c) | {"silent_fail": c.silent_fail} for c in sweep["cells"]],
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(out, indent=2) + "\n")
