using UnityEngine;
using UnityEditor;

public class ChipSpriteImporter : AssetPostprocessor
{
	private static string PathPrefix = "Assets/Chips/";

	protected void OnPreprocessTexture()
	{
		if ( !assetPath.StartsWith( PathPrefix ) )
			return;

		var textureImporter = (TextureImporter)assetImporter;
		textureImporter.spritePixelsPerUnit = 400;
	}
}