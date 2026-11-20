#if UNITY_EDITOR
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace Sitekick
{
	/// <summary>
	/// Two ways to keep a chip movie inside the Sitekick's face, rendered side by
	/// side so the choice is made on evidence:
	///
	///   left  — the frame SVG carries its own clipPath circle
	///   right — a plain full-bleed frame cropped by a SpriteMask made from the
	///           Sitekick's own body sprite
	///
	/// Writes Logs/pilot/clip-probe.txt and Logs/pilot/clip-probe.png.
	/// </summary>
	public static class ClipProbe
	{
		public const string ReportPath = "Logs/pilot/clip-probe.txt";

		public static void Run()
		{
			EditorSceneManager.OpenScene( ChipMovieCheck.ScenePath, OpenSceneMode.Single );
			foreach ( var r in Object.FindObjectsByType<SpriteRenderer>( FindObjectsSortMode.None ) )
				r.enabled = false;

			var camera = Camera.main;
			camera.clearFlags = CameraClearFlags.SolidColor;
			camera.backgroundColor = Color.black;
			camera.transform.position = new Vector3( 0f, 0f, -10f );

			var lines = new System.Text.StringBuilder();
			var shader = Shader.Find( "Unlit/VectorGradient" );
			var material = new Material( shader );

			var clipped = AssetDatabase.LoadAssetAtPath<Sprite>( "Assets/Pilot/clip_test.svg" );
			var square = AssetDatabase.LoadAssetAtPath<Sprite>( "Assets/Pilot/square_test.svg" );
			var body = AssetDatabase.LoadAssetAtPath<Sprite>( "Assets/Sitekick/Sprites/sitekick_body.png" );
			lines.AppendLine( "clip_test.svg " + ( clipped != null ) + ", square_test.svg " + ( square != null )
				+ ", body sprite " + ( body != null ) );

			// left: clipped frame, exactly as exported, drawn over the body's own
			// rectangle so a working clip shows as a disc inset in the blue square
			var left = new GameObject( "clip_left" );
			left.transform.position = new Vector3( -1.6f, 0f, 0f );
			left.transform.localScale = new Vector3( 2.75f / 3.75f, 2.5469f / 3.0f, 1f );
			var lsr = left.AddComponent<SpriteRenderer>();
			lsr.sprite = clipped;
			lsr.sharedMaterial = material;
			lines.AppendLine( "left  bounds " + lsr.bounds.size.ToString( "0.000" ) );

			// right: an unmasked square plus a sprite mask shaped like the body
			var right = new GameObject( "clip_right" );
			right.transform.position = new Vector3( 1.6f, 0f, 0f );
			right.transform.localScale = new Vector3( 2.75f / 3.75f, 2.5469f / 3.0f, 1f );
			var rsr = right.AddComponent<SpriteRenderer>();
			rsr.sprite = square;
			rsr.sharedMaterial = material;

			var maskObject = new GameObject( "body_mask" );
			maskObject.transform.position = right.transform.position;
			var mask = maskObject.AddComponent<SpriteMask>();
			mask.sprite = body;
			mask.alphaCutoff = 0.5f;
			lines.AppendLine( "mask sprite bounds " + ( body != null ? body.bounds.size.ToString( "0.000" ) : "-" ) );
			rsr.maskInteraction = SpriteMaskInteraction.VisibleInsideMask;

			var texture = new Texture2D( 1440, 1080, TextureFormat.RGB24, false );
			var cam = new GameObject( "probe_camera" ).AddComponent<Camera>();
			cam.CopyFrom( camera );
			cam.orthographic = true;
			cam.orthographicSize = 2.2f;
			cam.transform.position = new Vector3( 0f, 0f, -10f );
			cam.targetTexture = RenderTexture.GetTemporary( 1440, 1080, 24 );
			cam.Render();
			RenderTexture.active = cam.targetTexture;
			texture.ReadPixels( new Rect( 0, 0, 1440, 1080 ), 0, 0 );
			texture.Apply();
			File.WriteAllBytes( "Logs/pilot/clip-probe.png", texture.EncodeToPNG() );
			RenderTexture.active = null;
			cam.targetTexture.Release();

			// report what actually reached the picture on each side
			var pixels = texture.GetPixels();
			int leftBlue = 0, rightBlue = 0;
			for ( int y = 0; y < 1080; y++ )
			{
				for ( int x = 0; x < 1440; x++ )
				{
					var c = pixels[ y * 1440 + x ];
					if ( c.b > 0.4f && c.b > c.r * 1.5f )
					{
						if ( x < 720 ) leftBlue++;
						else rightBlue++;
					}
				}
			}
			lines.AppendLine( "blue pixels drawn  left " + leftBlue + "  right " + rightBlue
				+ "  (a full 300-px circle would be about 110000 at this camera)" );

			File.WriteAllText( ReportPath, lines.ToString() );
			Debug.Log( lines.ToString() );

			Object.DestroyImmediate( left );
			Object.DestroyImmediate( right );
			Object.DestroyImmediate( maskObject );
			Object.DestroyImmediate( cam.gameObject );
			Object.DestroyImmediate( material );
			Object.DestroyImmediate( texture );
		}
	}
}
#endif
